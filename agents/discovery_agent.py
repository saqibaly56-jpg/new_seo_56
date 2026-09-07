import json
from dataclasses import dataclass
from typing import List, Optional
from utils.openrouter import OpenRouterClient
from tenacity import retry, stop_after_attempt, wait_exponential

from utils.logger import get_logger
from config.settings import settings
from utils.db import get_db_connection, DB_PATH

logger = get_logger("discovery_agent")

@dataclass
class Candidate:
    game_name: str
    provider: str
    source_url: str
    airtable_record_id: Optional[str] = None
    featured_image_url: Optional[str] = None
    description_image_url: Optional[str] = None
    login_image_url: Optional[str] = None
    transaction_image_url: Optional[str] = None

class DiscoveryAgent:
    def __init__(self, user_id: int, user_settings: dict):
        self.user_id = user_id
        self.openrouter_client = OpenRouterClient(
            api_key=settings.openrouter_api_key,
            model=settings.openrouter_model,
        )
        
        # Ensure publish_history table exists in sqlite
        with get_db_connection(DB_PATH) as conn:
            # We add status to existing publish_history if possible or it relies on existing schema
            # Actually schema.sql defines publish_history without status initially. 
            # We'll just create the table if not exists with the new schema (SQLite ignores if exists)
            # To avoid schema conflicts on existing table, we'll try to add 'status' if missing, but simpler:
            # The prompt requested we use published_games or publish_history. We'll use publish_history.
            pass
            
    def _fetch_new_rows(self):
        """Fetches rows from SQLite links where status is 'New'"""
        with get_db_connection(DB_PATH) as conn:
            cursor = conn.execute("SELECT * FROM links WHERE user_id = ? AND status = 'New'", (self.user_id,))
            return [dict(row) for row in cursor.fetchall()]
        
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _extract_game_info(self, url: str) -> dict:
        """Uses OpenRouter to extract game_name and provider from a URL"""
        prompt = (
            f"Given this URL and any visible page context: {url}\n"
            "Extract the game name and provider name. "
            "Respond ONLY with JSON: {\"game_name\": \"...\", \"provider\": \"...\"}. "
            "If you cannot determine a field, use null."
        )
        
        response = self.openrouter_client.chat.completions.create(
            model=settings.openrouter_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content)

    def _is_duplicate(self, game_name: str, provider: str) -> bool:
        """Checks if the game is already in publish_history"""
        try:
            with get_db_connection(DB_PATH) as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM publish_history WHERE user_id = ? AND LOWER(game_name) = LOWER(?) AND LOWER(provider) = LOWER(?)",
                    (self.user_id, game_name, provider)
                )
                return cursor.fetchone() is not None
        except Exception:
            return False

    def discover_candidates(self) -> List[Candidate]:
        """
        Polls internal DB for new links, extracts metadata, checks duplicates, and returns Candidates.
        """
        candidates = []
        try:
            records = self._fetch_new_rows()
            logger.info(f"Discovered {len(records)} 'New' queued links.")
        except Exception as e:
            logger.error(f"Failed to fetch internal links: {e}")
            return []

        for record in records:
            record_id = record['id']
            url = record.get('url')
            
            if not url:
                continue
                
            # Immediately mark as Processing
            self.update_status(record_id, "Processing")
            
            game_name = record.get('game_name')
            provider = record.get('provider')
            
            if not game_name or not provider:
                try:
                    logger.info(f"Extracting info from URL via OpenRouter: {url}")
                    extracted = self._extract_game_info(url)
                    game_name = game_name or extracted.get("game_name")
                    provider = provider or extracted.get("provider")
                except Exception as e:
                    logger.error(f"OpenRouter extraction failed for {url}: {e}")
                    self.update_status(record_id, "Failed", "OpenRouter extraction failed")
                    continue
            
            if not game_name or not provider:
                logger.warning(f"Could not determine Game Name or Provider for {url}")
                self.update_status(record_id, "Failed", "Missing game or provider name")
                continue
                
            # Check deduplication
            if self._is_duplicate(game_name, provider):
                logger.info(f"Skipping {provider} - {game_name}: Duplicate found in DB.")
                self.update_status(record_id, "Failed", "duplicate")
                continue
                
            candidates.append(Candidate(
                game_name=game_name,
                provider=provider,
                source_url=url,
                airtable_record_id=str(record_id),
                featured_image_url=record.get('featured_image'),
                description_image_url=record.get('description_image'),
                login_image_url=record.get('login_image'),
                transaction_image_url=record.get('transaction_image')
            ))
            
        return candidates

    def update_status(self, record_id: str, status: str, notes: str = None):
        """Updates the SQLite links status"""
        try:
            with get_db_connection(DB_PATH) as conn:
                conn.execute(
                    "UPDATE links SET status = ?, status_reason = ? WHERE id = ?",
                    (status, notes, int(record_id))
                )
                conn.commit()
            logger.info(f"Link {record_id} marked as {status}.")
        except Exception as e:
            logger.error(f"Failed to update link status to {status} for {record_id}: {e}")

    def mark_published(self, record_id: str):
        """Legacy helper - Updates the record status to Published"""
        self.update_status(record_id, "Published")
