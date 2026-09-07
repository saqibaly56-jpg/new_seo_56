import os
import sys
import time
import uuid
import json
import shutil
import socket
import threading
import datetime
import traceback
from typing import Dict, Any, Optional

from utils.logger import get_logger
from utils.db_models import SessionLocal, Job, JobEvent, Worker, ContentDraft, WordPressSite, PublishHistory, SystemErrorLog, UsageRecord, CostRecord
from agents.discovery_agent import DiscoveryAgent, Candidate
from agents.research_agent import ResearchAgent
from agents.content_agent import ContentAgent, check_differentiation
from agents.fact_verification_agent import verify_claims, get_trusted_facts
from agents.image_agent import ImageAgent
from agents.compliance_agent import check_market_allowlist
from agents.wordpress_agent import WordPressPublisher
from core.universal_model import ContentDocument

logger = get_logger("job_worker")

WORKER_ID = f"worker-{socket.gethostname()}-{os.getpid()}"
WORKER_HEARTBEAT_INTERVAL = int(os.getenv("WORKER_HEARTBEAT_INTERVAL", "15"))
WORKER_HEARTBEAT_TIMEOUT = int(os.getenv("WORKER_HEARTBEAT_TIMEOUT", "45"))
WORKER_OFFLINE_TIMEOUT = int(os.getenv("WORKER_OFFLINE_TIMEOUT", "120"))

def emit_job_event(job_id: str, user_id: int, event_type: str, stage: str, status: str, message: str = "", worker_id: str = WORKER_ID, metadata: dict = None):
    """
    Creates a persistent JobEvent record in the database.
    """
    try:
        with SessionLocal() as db:
            event = JobEvent(
                job_id=job_id,
                user_id=user_id,
                event_type=event_type,
                stage=stage,
                status=status,
                message=message,
                worker_id=worker_id,
                metadata_json=json.dumps(metadata or {})
            )
            db.add(event)
            db.commit()
    except Exception as e:
        logger.error(f"Failed to emit job event for {job_id}: {e}")

def update_worker_heartbeat(status: str = "IDLE", current_job_id: str = None, current_stage: str = None):
    """
    Updates the Worker heartbeat record in the database.
    """
    try:
        now = datetime.datetime.utcnow()
        with SessionLocal() as db:
            worker = db.query(Worker).filter(Worker.id == WORKER_ID).first()
            if not worker:
                worker = Worker(
                    id=WORKER_ID,
                    worker_name=f"Worker-{os.getpid()}",
                    hostname=socket.gethostname(),
                    process_id=os.getpid(),
                    status=status,
                    current_job_id=current_job_id,
                    current_stage=current_stage,
                    started_at=now,
                    last_heartbeat=now
                )
                db.add(worker)
            else:
                worker.status = status
                worker.current_job_id = current_job_id
                worker.current_stage = current_stage
                worker.last_heartbeat = now
                worker.updated_at = now
            db.commit()
    except Exception as e:
        logger.error(f"Failed worker heartbeat update: {e}")

class HeartbeatThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.running = True

    def run(self):
        update_worker_heartbeat("IDLE")
        while self.running:
            time.sleep(WORKER_HEARTBEAT_INTERVAL)
            update_worker_heartbeat()

_heartbeat_thread = HeartbeatThread()
_heartbeat_thread.start()

def recover_abandoned_jobs():
    """
    Scans for jobs stuck in PROCESSING from stale or offline workers.
    """
    try:
        now = datetime.datetime.utcnow()
        stale_cutoff = now - datetime.timedelta(seconds=WORKER_HEARTBEAT_TIMEOUT)
        with SessionLocal() as db:
            processing_jobs = db.query(Job).filter(Job.status == "PROCESSING").all()
            for job in processing_jobs:
                if not job.started_at or job.started_at < stale_cutoff:
                    # Worker lost or timed out
                    if job.retry_count < job.max_retries:
                        job.status = "RETRYING"
                        job.retry_count += 1
                        db.commit()
                        emit_job_event(job.id, job.user_id, "JOB_RETRYING", job.current_stage or "QUEUED", "RETRYING", f"Worker timed out. Retrying attempt {job.retry_count}")
                        # Re-enqueue
                        from utils.queue import enqueue_job
                        enqueue_job(job.id, {
                            "user_id": job.user_id,
                            "game_name": job.game_name,
                            "provider": job.provider,
                            "target_market": job.target_market,
                            "site_id": job.site_id
                        })
                    else:
                        job.status = "FAILED"
                        job.failed_at = now
                        job.error_message = "Worker process timed out and max retries exceeded."
                        db.commit()
                        emit_job_event(job.id, job.user_id, "JOB_FAILED", job.current_stage or "FAILED", "FAILED", job.error_message)
    except Exception as e:
        logger.error(f"Error during abandoned job recovery: {e}")

def execute_job_task(job_id: str, payload: Dict[str, Any]):
    """
    Main background job execution task.
    Runs candidate discovery, research, fact processing (preserving fake-fact maker),
    content drafting, image processing, quality check, and draft creation.
    """
    logger.info(f"Worker {WORKER_ID} starting job {job_id}")
    user_id = payload.get("user_id")
    target_market = payload.get("target_market", "UK")
    site_id = payload.get("site_id")
    game_name = payload.get("game_name")
    provider = payload.get("provider")
    
    start_time = time.time()
    
    # Create isolated temp folder for job
    default_data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    if (
        os.getenv("APP_ENV", "development").strip().lower() in {"production", "prod"}
        or os.getenv("RAILWAY_ENVIRONMENT")
    ):
        default_data_dir = os.path.join("/tmp", "seo_automation")
    data_dir = os.getenv("DATA_DIR", default_data_dir)
    job_temp_dir = os.path.join(data_dir, "tmp", str(user_id), str(job_id))
    os.makedirs(job_temp_dir, exist_ok=True)
    
    update_worker_heartbeat("BUSY", current_job_id=job_id, current_stage="WORKER_ASSIGNED")
    emit_job_event(job_id, user_id, "WORKER_ASSIGNED", "WORKER_ASSIGNED", "PROCESSING", f"Assigned to worker {WORKER_ID}")
    
    with SessionLocal() as db:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            job = Job(
                id=job_id,
                user_id=user_id,
                site_id=site_id,
                game_name=game_name,
                provider=provider,
                target_market=target_market,
                status="PROCESSING",
                current_stage="JOB_STARTED",
                worker_id=WORKER_ID,
                started_at=datetime.datetime.utcnow()
            )
            db.add(job)
        else:
            job.status = "PROCESSING"
            job.current_stage = "JOB_STARTED"
            job.worker_id = WORKER_ID
            job.started_at = datetime.datetime.utcnow()
        db.commit()

    emit_job_event(job_id, user_id, "JOB_STARTED", "JOB_STARTED", "PROCESSING", "Job pipeline execution started.")
    
    try:
        # 1. Discovery Stage
        emit_job_event(job_id, user_id, "DISCOVERY_STARTED", "DISCOVERY", "PROCESSING")
        from dashboard.auth import get_user_settings
        user_settings = get_user_settings(user_id)
        
        candidate = Candidate(
            game_name=game_name or "Custom Game",
            provider=provider or "Custom Provider",
            source_url=payload.get("url", "https://example.com"),
            featured_image_url=payload.get("featured_image_url"),
            description_image_url=payload.get("description_image_url")
        )
        emit_job_event(job_id, user_id, "DISCOVERY_COMPLETED", "DISCOVERY", "PROCESSING", f"Candidate identified: {candidate.provider} - {candidate.game_name}")
        
        # 2. Research Stage
        emit_job_event(job_id, user_id, "RESEARCH_STARTED", "RESEARCH", "PROCESSING")
        research_agent = ResearchAgent()
        context = research_agent.gather_context(candidate)
        emit_job_event(job_id, user_id, "RESEARCH_COMPLETED", "RESEARCH", "PROCESSING", "Thematic context gathered.")
        
        # 3. Fact Processing Stage (PRESERVING FAKE-FACT MAKER INTACT)
        emit_job_event(job_id, user_id, "FACT_PROCESSING_STARTED", "FACT_PROCESSING", "PROCESSING", "Retrieving trusted facts or initializing fake-fact maker.")
        trusted_facts = get_trusted_facts(candidate.game_name, candidate.provider, user_id)
        if not trusted_facts:
            logger.info(f"No trusted facts for {candidate.game_name}. Fake-fact maker will generate realistic figures.")
            trusted_facts = {}
        emit_job_event(job_id, user_id, "FACT_PROCESSING_COMPLETED", "FACT_PROCESSING", "PROCESSING", "Fact processing complete.")
        
        
        # Load Template
        from utils.db_models import ContentTemplate, TemplateSection
        with SessionLocal() as db:
            template_dict = None
            tmpl = None
            if not tmpl:
                # Mimic UI fallback so image assignment section_ids perfectly match generated draft section_ids
                tmpl = db.query(ContentTemplate).filter(ContentTemplate.user_id == user_id, ContentTemplate.is_default == True).first()
                if not tmpl:
                    tmpl = db.query(ContentTemplate).filter(ContentTemplate.user_id == user_id).first()
                if not tmpl:
                    tmpl = db.query(ContentTemplate).first()
                    
            if tmpl:
                secs = []
                for s in tmpl.sections:
                    secs.append({
                        "id": str(s.id),
                        "name": s.name,
                        "required": s.required,
                        "content_type": s.content_type,
                        "ai_instruction": s.ai_instruction
                    })
                template_dict = {
                    "id": tmpl.id,
                    "name": tmpl.name,
                    "sections": secs
                }

        # 4. Content Generation Stage (Calls OpenRouter with prompt instructions)
        emit_job_event(job_id, user_id, "CONTENT_GENERATION_STARTED", "CONTENT_GENERATION", "PROCESSING", "Generating 1500+ word review with OpenRouter LLM.")
        content_agent = ContentAgent()
        draft_doc = content_agent.draft_article(candidate, context, trusted_facts, template=template_dict)
        emit_job_event(job_id, user_id, "CONTENT_GENERATION_COMPLETED", "CONTENT_GENERATION", "PROCESSING", f"Article generated: '{draft_doc.title}'")
        
        # 5. Image Processing Stage
        emit_job_event(job_id, user_id, "IMAGE_PROCESSING_STARTED", "IMAGE_PROCESSING", "PROCESSING")
        image_agent = ImageAgent()
        local_images = image_agent.process_images(candidate)
        draft_doc.images = local_images
        emit_job_event(job_id, user_id, "IMAGE_PROCESSING_COMPLETED", "IMAGE_PROCESSING", "PROCESSING", f"Processed {len(local_images)} images.")
        
        # 6. Quality Check Stage
        emit_job_event(job_id, user_id, "QUALITY_CHECK_STARTED", "QUALITY_CHECK", "PROCESSING")
        differentiation_ok = check_differentiation(draft_doc)
        compliance_ok = check_market_allowlist(target_market)
        if not differentiation_ok or not compliance_ok:
            raise ValueError("Generated article failed quality or market compliance checks")
        emit_job_event(job_id, user_id, "QUALITY_CHECK_COMPLETED", "QUALITY_CHECK", "PROCESSING", "Quality & Compliance checks passed.")
        
        # 7. Save Draft & Set Status to PENDING_REVIEW
        duration = time.time() - start_time
        now = datetime.datetime.utcnow()
        
        with SessionLocal() as db:
            new_draft = ContentDraft(
                user_id=user_id,
                site_id=site_id,
                job_id=job_id,
                game_name=candidate.game_name,
                provider=candidate.provider,
                document_json=draft_doc.model_dump_json(),
                status="draft"
            )
            db.add(new_draft)
            
            job_record = db.query(Job).filter(Job.id == job_id).first()
            if job_record:
                job_record.status = "PENDING_REVIEW"
                job_record.current_stage = "PENDING_REVIEW"
                job_record.completed_at = now
                job_record.duration = duration
                
            # Log Usage & Cost Records
            usage = UsageRecord(
                user_id=user_id,
                job_id=job_id,
                event_type="ai_generation",
                units=1,
                tokens_used=4000,
                estimated_cost=0.03
            )
            cost = CostRecord(
                user_id=user_id,
                job_id=job_id,
                category="openrouter_llm",
                amount=0.03,
                description=f"Generated draft for {candidate.game_name}"
            )
            db.add(usage)
            db.add(cost)
            
            # Increment worker completed count
            worker_record = db.query(Worker).filter(Worker.id == WORKER_ID).first()
            if worker_record:
                worker_record.jobs_completed += 1
                worker_record.status = "IDLE"
                worker_record.current_job_id = None
                worker_record.current_stage = None
                
            db.commit()
            
        emit_job_event(job_id, user_id, "PENDING_REVIEW", "PENDING_REVIEW", "PENDING_REVIEW", f"Draft generated in {duration:.2f}s. Pending user review.")
        emit_job_event(job_id, user_id, "JOB_COMPLETED", "COMPLETED", "PENDING_REVIEW", "Job processing finished successfully.")
        
    except Exception as e:
        duration = time.time() - start_time
        err_msg = str(e)
        err_trace = traceback.format_exc()
        logger.error(f"Job {job_id} failed: {err_msg}")
        logger.error(err_trace)
        
        now = datetime.datetime.utcnow()
        with SessionLocal() as db:
            job_record = db.query(Job).filter(Job.id == job_id).first()
            if job_record:
                job_record.status = "FAILED"
                job_record.current_stage = "FAILED"
                job_record.failed_at = now
                job_record.error_message = err_msg
                job_record.duration = duration
                
            error_log = SystemErrorLog(
                user_id=user_id,
                job_id=job_id,
                category="Worker",
                error_code="WORKER_EXECUTION_ERROR",
                message=err_msg,
                stack_trace=err_trace
            )
            db.add(error_log)
            
            worker_record = db.query(Worker).filter(Worker.id == WORKER_ID).first()
            if worker_record:
                worker_record.jobs_failed += 1
                worker_record.status = "IDLE"
                worker_record.current_job_id = None
                worker_record.current_stage = None
                
            db.commit()
            
        emit_job_event(job_id, user_id, "JOB_FAILED", "FAILED", "FAILED", f"Job failed: {err_msg}")
        
    finally:
        # Cleanup isolated temp directory
        try:
            if os.path.exists(job_temp_dir):
                shutil.rmtree(job_temp_dir)
        except Exception:
            pass
            
        update_worker_heartbeat("IDLE", current_job_id=None, current_stage=None)
