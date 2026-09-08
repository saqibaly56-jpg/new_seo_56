import os
import uuid
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from utils.logger import get_logger

logger = get_logger("queue_utils")

def get_redis_url() -> str:
    """Return the configured Redis URL, supporting Railway component variables."""
    redis_url = os.getenv("REDIS_URL", "").strip()
    if redis_url and "your_redis_private_host" not in redis_url and "my-redis.internal" not in redis_url:
        return redis_url

    redis_host = os.getenv("REDISHOST", "").strip()
    redis_port = os.getenv("REDISPORT", "6379").strip()
    redis_user = os.getenv("REDISUSER", "default").strip()
    redis_password = os.getenv("REDISPASSWORD") or os.getenv("REDIS_PASSWORD")
    if redis_host and redis_password:
        from urllib.parse import quote
        return f"redis://{quote(redis_user, safe='')}:{quote(redis_password, safe='')}@{redis_host}:{redis_port}/0"

    return redis_url or "redis://localhost:6379/0"


REDIS_URL = get_redis_url()

_redis_conn = None
_rq_queue = None
_use_redis = False

try:
    import redis
    from rq import Queue
    r = redis.from_url(REDIS_URL, socket_connect_timeout=2)
    r.ping()
    _redis_conn = r
    _rq_queue = Queue("seo_automation_queue", connection=_redis_conn)
    _use_redis = True
    logger.info("Connected to Redis Queue server successfully.")
except Exception as e:
    logger.warning(f"Redis Queue connection failed ({e}). Operating in Local Thread Queue Fallback mode.")
    _use_redis = False

def is_redis_available() -> bool:
    return _use_redis

def enqueue_job(job_id: str, payload: Dict[str, Any]) -> bool:
    """
    Enqueues a job payload for execution by the background worker.
    """
    if _use_redis and _rq_queue:
        try:
            from workers.job_worker import execute_job_task
            _rq_queue.enqueue(execute_job_task, job_id, payload, job_id=job_id, job_timeout=600)
            logger.info(f"Job {job_id} successfully enqueued into Redis Queue.")
            return True
        except Exception as e:
            logger.error(f"Failed to enqueue job {job_id} into Redis: {e}")
            
    if os.getenv("APP_ENV", "development").strip().lower() in {"production", "prod"}:
        logger.error(f"Job {job_id} was not enqueued because Redis is unavailable in production.")
        return False

    # Fallback to background thread execution if Redis is not running locally
    import threading
    from workers.job_worker import execute_job_task
    t = threading.Thread(target=execute_job_task, args=(job_id, payload), daemon=True)
    t.start()
    logger.info(f"Job {job_id} enqueued via Local Background Thread fallback.")
    return True
