import argparse
import json
from collections import Counter
import traceback
import time
from utils.logger import get_logger
from utils.db import init_db
from agents.discovery_agent import DiscoveryAgent, Candidate
from pipelines.content_pipeline import run_single_candidate
from utils.db_models import SessionLocal, ContentDraft, WordPressSite

logger = get_logger("orchestrator")

def run(target_market: str, max_volume: int, dry_run: bool, user_id: int = 1):
    logger.info(f"Starting orchestration run (Market: {target_market}, Max Volume: {max_volume}, Dry Run: {dry_run}, User ID: {user_id})")
    init_db()

    from dashboard.auth import get_user_settings
    user_settings = get_user_settings(user_id) if user_id else {}
    if not user_settings:
        logger.warning(f"No user settings found for User ID: {user_id}; continuing with defaults.")
        user_settings = {}
    
    discovery = DiscoveryAgent(user_id=user_id, user_settings=user_settings)
    candidates = discovery.discover_candidates()
    if not candidates and dry_run:
        logger.info("Dry run with no queued links detected; using safe default demo candidates.")
        candidates = [
            Candidate(game_name="Sweet Bonanza 1000", provider="Pragmatic Play", source_url="https://example.com/sweet-bonanza-1000"),
            Candidate(game_name="Sugar Rush", provider="Pragmatic Play", source_url="https://example.com/sugar-rush"),
        ]

    processed = 0
    metrics = Counter()
    
    for candidate in candidates:
        if processed >= max_volume:
            logger.info(f"Reached max volume of {max_volume}. Stopping run.")
            break
            
        logger.info(f"Processing candidate: {candidate.game_name}")
        
        try:
            start_time = time.time()
            draft, status = run_single_candidate(candidate, target_market=target_market, user_id=user_id, user_settings=user_settings, dry_run=dry_run)
            metrics[status] += 1
            duration = time.time() - start_time
            
            if status == "SUCCESS":
                processed += 1
                
                # Save draft to database
                with SessionLocal() as db:
                    # Get the default site ID
                    site = db.query(WordPressSite).filter(WordPressSite.user_id == user_id).first()
                    site_id = site.id if site else None
                    
                    new_draft = ContentDraft(
                        user_id=user_id,
                        site_id=site_id,
                        game_name=candidate.game_name,
                        provider=candidate.provider,
                        document_json=draft.model_dump_json(),
                        status="draft"
                    )
                    db.add(new_draft)
                    db.commit()
                
                logger.info(f"Successfully processed and drafted {candidate.game_name}. Pending Review. Duration: {duration:.2f}s")
                if candidate.airtable_record_id:
                    if not dry_run:
                        discovery.update_status(candidate.airtable_record_id, "Pending Review")
                    else:
                        discovery.update_status(candidate.airtable_record_id, "New", "Dry Run Success")
            else:
                if candidate.airtable_record_id:
                    discovery.update_status(candidate.airtable_record_id, "Failed", f"Pipeline Status: {status}")
        except Exception as e:
            metrics["UNHANDLED_EXCEPTION"] += 1
            logger.error(f"Unhandled exception processing {candidate.game_name}: {e}")
            logger.error(traceback.format_exc())
            if candidate.airtable_record_id:
                discovery.update_status(candidate.airtable_record_id, "Failed", "Unhandled Exception")
            
    logger.info(f"Orchestration run complete. Total drafts pushed: {processed}")
    logger.info(f"Run Summary Metrics: {json.dumps(dict(metrics))}")
    return processed

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Autonomous Casino Content Orchestrator")
    parser.add_argument("--market", type=str, default="UK", help="Target market for compliance check")
    parser.add_argument("--volume", type=int, default=2, help="Maximum number of drafts to push per run")
    parser.add_argument("--dry-run", action="store_true", help="Run without mutating external APIs (WordPress)")
    parser.add_argument("--user-id", type=int, required=True, help="User ID running the automation")
    
    args = parser.parse_args()
    
    run(target_market=args.market, max_volume=args.volume, dry_run=args.dry_run, user_id=args.user_id)
