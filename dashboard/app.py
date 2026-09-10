import os
import sys
import uuid
import shutil
import datetime
import json
import html
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, BackgroundTasks, File, Form, UploadFile, Depends, HTTPException, status, Response, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from utils.db import get_db_connection, init_db
from utils.db_models import SessionLocal, User, UserSettings, WordPressSite, ContentDraft, PublishHistory, Job, JobEvent, Worker, AuditLog, Subscription, UsageRecord, SystemErrorLog, CostRecord, ImageAsset, ImageAssignment, TemplateSection, ContentTemplate
from dashboard.auth import hash_password, verify_password, generate_session_token, get_current_user_id, get_current_user, require_admin, log_audit_event, get_user_settings
from utils.crypto import encrypt_credential, decrypt_credential
from utils.queue import enqueue_job, is_redis_available
from services.subscription_service import check_user_quota, get_user_usage_summary, get_or_create_subscription
from core.universal_model import ContentTemplateCreate, ImageAssignmentCreate, WebsiteProfileSchema, ContentDocument
from core.rendering_engine import RenderingEngine
from utils.logger import get_logger

logger = get_logger("dashboard")

# Initialize app and DB
init_db()
app = FastAPI(title="SEO Automation Multi-Tenant SaaS Engine")

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = uuid.uuid4().hex[:12]
    logger.exception("Unhandled request error %s for %s %s", request_id, request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error. Please retry or contact support.",
            "request_id": request_id,
        },
    )

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_default_data_dir = os.path.join(BASE_DIR, 'data')
if (
    os.getenv('APP_ENV', 'development').strip().lower() in {'production', 'prod'}
    or os.getenv('RAILWAY_ENVIRONMENT')
):
    _default_data_dir = os.path.join('/tmp', 'seo_automation')
DATA_DIR = os.getenv("DATA_DIR", _default_data_dir)
DB_PATH = os.path.join(DATA_DIR, 'history.db')
STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')

os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/healthz")
def health_check():
    return {"status": "ok"}

class RunConfig(BaseModel):
    market: str = "UK"
    volume: int = 2
    game_name: Optional[str] = "Sweet Bonanza"
    provider: Optional[str] = "Pragmatic Play"
    site_id: Optional[int] = None
    dry_run: bool = False

class UserCreate(BaseModel):
    email: str
    password: str

class SettingsUpdate(BaseModel):
    wp_url: str
    wp_username: str
    wp_app_password: str
    theme_type: str = "standard"
    seo_plugin: str = "none"

# Ensure seed admin user exists only in non-production local/dev environments.
def seed_admin_user():
    try:
        configured_app_env = os.getenv("APP_ENV")
        app_env = (configured_app_env or "").strip().lower()
        if not configured_app_env or app_env in {"production", "prod"} or os.getenv("RAILWAY_ENVIRONMENT"):
            return

        with SessionLocal() as db:
            admin = db.query(User).filter(User.role == "admin").first()
            if not admin:
                admin_email = os.getenv("ADMIN_EMAIL", "admin@seoautomation.com")
                admin_pass = os.getenv("ADMIN_PASSWORD", "AdminPass123!")
                hashed = hash_password(admin_pass)
                new_admin = User(
                    email=admin_email,
                    password_hash=hashed,
                    role="admin",
                    subscription_plan="business",
                    is_active=True
                )
                db.add(new_admin)
                db.commit()
    except Exception:
        pass

seed_admin_user()

@app.get("/")
def read_root():
    index_file = os.path.join(STATIC_DIR, 'index.html')
    if os.path.exists(index_file):
        with open(index_file, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Welcome to SEO Automation Dashboard</h1>")

@app.get("/dashboard")
def dashboard_page():
    return read_root()

@app.get("/openseo")
def openseo_page(request: Request):
    """Open the independently deployed OpenSEO workspace."""
    configured_url = os.getenv("OPENSEO_URL")
    request_host = (request.url.hostname or "").lower()
    if configured_url:
        openseo_url = configured_url
    elif request_host in {"localhost", "127.0.0.1", "::1"}:
        openseo_url = "http://localhost:3001"
    else:
        openseo_url = "https://app.openseo.so"
    return RedirectResponse(url=openseo_url.rstrip("/"), status_code=307)

@app.get("/seo-beta")
def seo_beta_page(request: Request):
    """Open the separately deployed SEO Optimization Beta workspace."""
    configured_url = os.getenv("SEO_BETA_URL")
    request_host = (request.url.hostname or "").lower()
    if configured_url:
        beta_url = configured_url
    elif request_host in {"localhost", "127.0.0.1", "::1"}:
        beta_url = "http://localhost:3002"
    else:
        raise HTTPException(status_code=503, detail="SEO_BETA_URL is not configured")
    return RedirectResponse(url=beta_url.rstrip("/"), status_code=307)

@app.get("/admin")
def admin_page(user = Depends(require_admin)):
    file_path = os.path.join(STATIC_DIR, 'admin.html')
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Admin Dashboard HTML not found in static folder</h1>", status_code=404)

@app.get("/login.html")
def login_page():
    file_path = os.path.join(STATIC_DIR, 'login.html')
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Not Found</h1>", status_code=404)

@app.get("/register.html")
def register_page():
    file_path = os.path.join(STATIC_DIR, 'register.html')
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Not Found</h1>", status_code=404)

@app.post("/api/register")
def register_user(user: UserCreate, request: Request):
    try:
        with SessionLocal() as db:
            existing = db.query(User).filter(User.email == user.email).first()
            if existing:
                raise HTTPException(status_code=400, detail="Email already registered")
                
            hashed_pw = hash_password(user.password)
            new_user = User(
                email=user.email,
                password_hash=hashed_pw,
                role="user",
                subscription_plan="free"
            )
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            
            # Create UserSettings and Subscription
            new_settings = UserSettings(user_id=new_user.id)
            new_sub = Subscription(user_id=new_user.id, plan="free", article_limit=5)
            db.add(new_settings)
            db.add(new_sub)
            db.commit()

            from services.template_service import seed_default_template
            seed_default_template(new_user.id)
            
            log_audit_event(new_user.id, "USER_REGISTERED", "User", str(new_user.id), request.client.host if request.client else None)
            return {"message": "User registered successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/login")
def login(user: UserCreate, response: Response, request: Request):
    with SessionLocal() as db:
        u = db.query(User).filter(User.email == user.email).first()
        if not u or not verify_password(user.password, u.password_hash):
            raise HTTPException(status_code=401, detail="Incorrect email or password")
            
        if not u.password_hash.startswith("pbkdf2:sha256:"):
            u.password_hash = hash_password(user.password)
            
        token = generate_session_token()
        with get_db_connection() as conn:
            conn.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, u.id))
            conn.commit()
            
        response.set_cookie(key="session_token", value=token, httponly=True, samesite="lax", max_age=604800)
        log_audit_event(u.id, "USER_LOGIN", "User", str(u.id), request.client.host if request.client else None)
        return {"message": "Login successful", "role": u.role}

@app.post("/api/logout")
def logout(response: Response, user_id: int = Depends(get_current_user_id), request: Request = None):
    if request:
        token = request.cookies.get("session_token")
        if token:
            with get_db_connection() as conn:
                conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
                conn.commit()
    response.delete_cookie("session_token")
    return {"message": "Logout successful"}

@app.post("/api/settings")
def update_settings(settings: SettingsUpdate, user_id: int = Depends(get_current_user_id)):
    encrypted_password = encrypt_credential(settings.wp_app_password)
    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO user_settings (user_id, wp_url, wp_username, wp_app_password, theme_type, seo_plugin)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (user_id) DO UPDATE SET
                wp_url = excluded.wp_url,
                wp_username = excluded.wp_username,
                wp_app_password = excluded.wp_app_password,
                theme_type = excluded.theme_type,
                seo_plugin = excluded.seo_plugin
        """, (
            user_id,
            settings.wp_url,
            settings.wp_username,
            encrypted_password,
            settings.theme_type,
            settings.seo_plugin,
        ))
        conn.commit()

    with SessionLocal() as db:
        # Upsert WordPressSite record
        site = db.query(WordPressSite).filter(WordPressSite.user_id == user_id, WordPressSite.site_url == settings.wp_url).first()
        if not site:
            site = WordPressSite(
                user_id=user_id,
                site_url=settings.wp_url,
                username=settings.wp_username,
                app_password=encrypted_password,
                editor_type=settings.theme_type,
                seo_plugin=settings.seo_plugin
            )
            db.add(site)
        else:
            site.username = settings.wp_username
            site.app_password = encrypted_password
            site.seo_plugin = settings.seo_plugin
        db.commit()
        
    log_audit_event(user_id, "SETTINGS_UPDATED", "UserSettings", str(user_id))
    return {"message": "Settings updated"}

@app.get("/api/settings")
def get_settings_handler(user_id: int = Depends(get_current_user_id)):
    with get_db_connection() as conn:
        result = conn.execute("SELECT wp_url, wp_username, wp_app_password, theme_type, seo_plugin FROM user_settings WHERE user_id = ?", (user_id,))
        row = result.fetchone()
        if not row:
            return {}
        data = dict(row)
        if data.get('wp_app_password'):
            data['wp_app_password'] = decrypt_credential(data['wp_app_password'])
        return data

# --- JOB ENQUEUEING & REDIS QUEUE SYSTEM ---

@app.post("/api/run")
def trigger_run(config: RunConfig, user_id: int = Depends(get_current_user_id)):
    # 1. Quota Check
    if not check_user_quota(user_id):
        raise HTTPException(status_code=402, detail="Monthly article generation limit reached for your plan. Please upgrade.")
        
    job_id = f"job-{uuid.uuid4().hex[:12]}"
    now = datetime.datetime.utcnow()
    
    with SessionLocal() as db:
        new_job = Job(
            id=job_id,
            user_id=user_id,
            site_id=config.site_id,
            game_name=config.game_name or "Sweet Bonanza",
            provider=config.provider or "Pragmatic Play",
            target_market=config.market,
            status="QUEUED",
            current_stage="QUEUED",
            created_at=now
        )
        db.add(new_job)
        
        # Record JOB_CREATED and JOB_QUEUED events
        event1 = JobEvent(job_id=job_id, user_id=user_id, event_type="JOB_CREATED", stage="QUEUED", status="QUEUED", message="Job record created in database.")
        event2 = JobEvent(job_id=job_id, user_id=user_id, event_type="JOB_QUEUED", stage="QUEUED", status="QUEUED", message="Enqueued into Redis queue worker.")
        db.add(event1)
        db.add(event2)
        db.commit()
        
    payload = {
        "job_id": job_id,
        "user_id": user_id,
        "url": getattr(config, 'url', None),
        "game_name": config.game_name or "Sweet Bonanza",
        "provider": config.provider or "Pragmatic Play",
        "target_market": config.market,
        "site_id": config.site_id,
        "dry_run": config.dry_run
    }
    
    if not enqueue_job(job_id, payload):
        with SessionLocal() as db:
            job_record = db.query(Job).filter(Job.id == job_id).first()
            if job_record:
                job_record.status = "FAILED"
                job_record.current_stage = "QUEUE"
                job_record.error_message = "Job queue is unavailable. Configure Redis before retrying."
                job_record.failed_at = datetime.datetime.utcnow()
                db.commit()
        raise HTTPException(status_code=503, detail="Job queue is unavailable. Please configure Redis and retry.")
    log_audit_event(user_id, "JOB_TRIGGERED", "Job", job_id, details=config.dict())
    
    return {"message": "Job enqueued successfully", "job_id": job_id, "status": "QUEUED"}

class ActiveFormatRequest(BaseModel):
    mode: str = "default" # "default" or "custom"
    template_id: Optional[int] = None
    save_as_active: bool = True

@app.get("/api/user/active-format")
def get_user_active_format(user_id: int = Depends(get_current_user_id)):
    from utils.db_models import ContentTemplate
    with SessionLocal() as db:
        settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
        mode = settings.active_format_mode if (settings and settings.active_format_mode) else "default"
        template_id = settings.active_template_id if settings else None
        
        template_name = "Default SEO Format"
        if mode == "custom" and template_id:
            tmpl = db.query(ContentTemplate).filter(ContentTemplate.id == template_id).first()
            if tmpl:
                template_name = tmpl.name
            else:
                mode = "default"
                template_id = None
                
        return {
            "mode": mode,
            "template_id": template_id,
            "template_name": template_name,
            "is_active_saved": True
        }

@app.post("/api/user/active-format")
def set_user_active_format(req: ActiveFormatRequest, user_id: int = Depends(get_current_user_id)):
    with SessionLocal() as db:
        settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
        if not settings:
            settings = UserSettings(user_id=user_id)
            db.add(settings)
            
        if req.save_as_active:
            settings.active_format_mode = req.mode
            settings.active_template_id = req.template_id
            db.commit()
            log_audit_event(user_id, "ACTIVE_FORMAT_SAVED", "UserSettings", str(user_id), details={"mode": req.mode, "template_id": req.template_id})
            
        return {
            "message": "Active format updated in database",
            "mode": req.mode,
            "template_id": req.template_id,
            "saved_permanently": req.save_as_active
        }

class ContentSettingsRequest(BaseModel):
    default_market: Optional[str] = "UK"
    default_word_count: Optional[str] = "1500"
    default_tone: Optional[str] = "professional"
    default_keyword_density: Optional[str] = "1.2"
    save_as_default: bool = True

@app.get("/api/user/content-settings")
def get_user_content_settings(user_id: int = Depends(get_current_user_id)):
    with SessionLocal() as db:
        settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
        return {
            "default_market": settings.default_market if settings and settings.default_market else "UK",
            "default_word_count": settings.default_word_count if settings and settings.default_word_count else "1500",
            "default_tone": settings.default_tone if settings and settings.default_tone else "professional",
            "default_keyword_density": settings.default_keyword_density if settings and settings.default_keyword_density else "1.2"
        }

@app.post("/api/user/content-settings")
def set_user_content_settings(req: ContentSettingsRequest, user_id: int = Depends(get_current_user_id)):
    with SessionLocal() as db:
        settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
        if not settings:
            settings = UserSettings(user_id=user_id)
            db.add(settings)
            
        if req.save_as_default:
            if req.default_market: settings.default_market = req.default_market
            if req.default_word_count: settings.default_word_count = req.default_word_count
            if req.default_tone: settings.default_tone = req.default_tone
            if req.default_keyword_density: settings.default_keyword_density = req.default_keyword_density
            db.commit()
            log_audit_event(user_id, "CONTENT_SETTINGS_SAVED", "UserSettings", str(user_id), details=req.dict())
            
        return {"message": "Content setup settings saved to database successfully"}

# --- TENANT-ISOLATED USER DASHBOARD APIS ---

@app.delete("/api/user/jobs/clear")
def clear_user_jobs(user_id: int = Depends(get_current_user_id)):
    with SessionLocal() as db:
        # Delete jobs that are COMPLETED, FAILED, or PENDING_REVIEW
        jobs_to_delete = db.query(Job).filter(
            Job.user_id == user_id,
            Job.status.in_(["COMPLETED", "FAILED", "PENDING_REVIEW"])
        ).all()
        job_ids = [job.id for job in jobs_to_delete]
        if job_ids:
            db.query(JobEvent).filter(JobEvent.job_id.in_(job_ids)).delete(synchronize_session=False)
        for j in jobs_to_delete:
            db.delete(j)
        db.commit()
        return {"status": "success", "deleted": len(jobs_to_delete)}

@app.get("/api/user/jobs")
def get_user_jobs(status_filter: Optional[str] = None, user_id: int = Depends(get_current_user_id)):
    with SessionLocal() as db:
        query = db.query(Job).filter(Job.user_id == user_id)
        if status_filter and status_filter.lower() != "all":
            query = query.filter(Job.status == status_filter.upper())
        jobs = query.order_by(Job.created_at.desc()).limit(50).all()
        return [
            {
                "job_id": j.id,
                "game_name": j.game_name,
                "provider": j.provider,
                "status": j.status,
                "current_stage": j.current_stage,
                "worker_id": j.worker_id,
                "retry_count": j.retry_count,
                "duration": j.duration,
                "error_message": j.error_message,
                "created_at": j.created_at.strftime("%Y-%m-%d %H:%M:%S") if j.created_at else None
            }
            for j in jobs
        ]

@app.get("/api/user/jobs/{job_id}/timeline")
def get_job_timeline(job_id: str, user = Depends(get_current_user)):
    with SessionLocal() as db:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
            
        if user.role != "admin" and job.user_id != user.id:
            raise HTTPException(status_code=403, detail="Forbidden: You do not own this job")
            
        events = db.query(JobEvent).filter(JobEvent.job_id == job_id).order_by(JobEvent.created_at.asc()).all()
        return {
            "job_id": job.id,
            "status": job.status,
            "game_name": job.game_name,
            "provider": job.provider,
            "timeline": [
                {
                    "id": e.id,
                    "event_type": e.event_type,
                    "stage": e.stage,
                    "status": e.status,
                    "message": e.message,
                    "worker_id": e.worker_id,
                    "timestamp": e.created_at.strftime("%Y-%m-%d %H:%M:%S") if e.created_at else None
                }
                for e in events
            ]
        }

@app.get("/api/user/usage")
def get_user_usage(user_id: int = Depends(get_current_user_id)):
    return get_user_usage_summary(user_id)

@app.get("/api/user/sites")
def get_user_sites(user_id: int = Depends(get_current_user_id)):
    with SessionLocal() as db:
        sites = db.query(WordPressSite).filter(WordPressSite.user_id == user_id).all()
        return [
            {
                "id": s.id,
                "site_url": s.site_url,
                "username": s.username,
                "editor_type": s.editor_type,
                "seo_plugin": s.seo_plugin,
                "status": s.status,
                "created_at": s.created_at.strftime("%Y-%m-%d") if s.created_at else None
            }
            for s in sites
        ]

@app.get("/api/user/errors")
def get_user_errors(user_id: int = Depends(get_current_user_id)):
    with SessionLocal() as db:
        logs = db.query(SystemErrorLog).filter(SystemErrorLog.user_id == user_id).order_by(SystemErrorLog.created_at.desc()).limit(30).all()
        return [
            {
                "id": err.id,
                "job_id": err.job_id,
                "category": err.category,
                "error_code": err.error_code,
                "message": err.message,
                "timestamp": err.created_at.strftime("%Y-%m-%d %H:%M:%S") if err.created_at else None
            }
            for err in logs
        ]

@app.get("/api/drafts")
def get_drafts(user_id: int = Depends(get_current_user_id)):
    with SessionLocal() as db:
        drafts = db.query(ContentDraft).filter(ContentDraft.user_id == user_id).order_by(ContentDraft.created_at.desc()).all()
        result = []
        for d in drafts:
            doc = None
            if d.document_json:
                try:
                    doc = json.loads(d.document_json)
                except:
                    pass

            html_content = ""
            if doc:
                try:
                    html_content = RenderingEngine.render_classic_html(ContentDocument(**doc))
                except Exception as exc:
                    logger.warning(f"Unable to render draft {d.id}: {exc}")
            
            result.append({
                "id": d.id,
                "game_name": d.game_name,
                "provider": d.provider,
                "status": d.status,
                "title": doc.get("title", "") if doc else "",
                "html_content": html_content,
                "created_at": d.created_at.strftime("%Y-%m-%d %H:%M") if d.created_at else None
            })
        return result

class DraftUpdate(BaseModel):
    title: str
    html_content: str

@app.put("/api/drafts/{draft_id}")
def update_draft(draft_id: int, payload: DraftUpdate, user_id: int = Depends(get_current_user_id)):
    with SessionLocal() as db:
        draft = db.query(ContentDraft).filter(ContentDraft.id == draft_id, ContentDraft.user_id == user_id).first()
        if not draft:
            raise HTTPException(status_code=404, detail="Draft not found")
        
        doc = {}
        if draft.document_json:
            try:
                doc = json.loads(draft.document_json)
            except:
                pass
        
        doc["title"] = payload.title
        doc["html_content"] = payload.html_content
        draft.document_json = json.dumps(doc)
        
        db.commit()
        return {"message": "Draft updated successfully"}

@app.delete("/api/drafts/{draft_id}")
def delete_draft(draft_id: int, user_id: int = Depends(get_current_user_id)):
    with SessionLocal() as db:
        draft = db.query(ContentDraft).filter(ContentDraft.id == draft_id, ContentDraft.user_id == user_id).first()
        if not draft:
            raise HTTPException(status_code=404, detail="Draft not found")
        # Also delete associated image assignments
        db.query(ImageAssignment).filter(ImageAssignment.draft_id == draft_id).delete()
        db.delete(draft)
        db.commit()
        return {"message": "Draft deleted successfully"}

@app.post("/api/publish/{draft_id}")
def publish_draft(draft_id: int, action: str = "publish", user_id: int = Depends(get_current_user_id)):
    from core.universal_model import ContentDocument
    from agents.wordpress_agent import WordPressPublisher
    
    with SessionLocal() as db:
        from utils.db_models import ContentDraft, PublishHistory, ImageAssignment, ImageAsset, WordPressSite
        draft_record = db.query(ContentDraft).filter(ContentDraft.id == draft_id, ContentDraft.user_id == user_id).first()
        if not draft_record:
            raise HTTPException(status_code=404, detail="Draft not found")
            
        if draft_record.status == "published":
            raise HTTPException(status_code=400, detail="Draft is already published")
            
        user_settings = get_user_settings(user_id)
        if not user_settings or not user_settings.get('wp_url'):
            raise HTTPException(status_code=400, detail="No WordPress site configured in user settings.")
            
        wp_site_query = db.query(WordPressSite).filter(WordPressSite.user_id == user_id)
        if draft_record.site_id:
            wp_site_query = wp_site_query.filter(WordPressSite.id == draft_record.site_id)
        else:
            wp_site_query = wp_site_query.filter(WordPressSite.site_url == user_settings.get('wp_url'))
        wp_site = wp_site_query.first()
        if draft_record.site_id and not wp_site:
            raise HTTPException(status_code=403, detail="The draft's WordPress site is not available to this user.")
        active_theme = wp_site.active_theme if wp_site and wp_site.active_theme else "unknown"

        site_profile = {
            "site_url": user_settings.get('wp_url', ''),
            "username": user_settings.get('wp_username', ''),
            "app_password": user_settings.get('wp_app_password', ''),
            "editor_type": user_settings.get('theme_type', 'classic'),
            "seo_plugin": user_settings.get('seo_plugin', 'none'),
            "active_theme": active_theme
        }
        
        doc_data = json.loads(draft_record.document_json)
        doc = ContentDocument(**doc_data)

        from services.validation_service import validate_content_before_publish
        validation = validate_content_before_publish(
            doc,
            user_id,
            site_id=draft_record.site_id,
            draft_id=draft_id,
            job_id=draft_record.job_id,
            strict=action == "publish",
        )
        if not validation.is_valid:
            raise HTTPException(status_code=422, detail={"message": "Draft failed publish validation.", "errors": validation.errors, "warnings": validation.warnings})
        
        if active_theme and 'appyn' in active_theme.lower():
            from adapters.themes.appyn import AppynAdapter
            AppynAdapter.ensure_custom_fields(doc)
        
        # Load Image Assignments
        assignments_db = db.query(ImageAssignment).filter(ImageAssignment.draft_id == draft_id).all()
        if not assignments_db and draft_record.job_id:
            assignments_db = db.query(ImageAssignment).filter(ImageAssignment.job_id == draft_record.job_id).all()
            
        image_assignments = []
        for a in assignments_db:
            image_asset = db.query(ImageAsset).filter(ImageAsset.id == a.image_id).first()
            if image_asset:
                image_assignments.append({
                    "section_id": a.section_id,
                    "section_name": "", 
                    "url": None,
                    "file_path": image_asset.file_path,
                    "alignment": a.alignment,
                    "size": a.size,
                    "custom_width": a.custom_width,
                    "custom_height": a.custom_height,
                    "position": a.position,
                    "fallback_behavior": a.fallback_behavior
                })
        
        wp_publisher = WordPressPublisher(site_profile=site_profile)
        article_id = wp_publisher.publish(doc, image_assignments, post_status=action)

        if wp_publisher.last_errors:
            raise HTTPException(status_code=502, detail={"message": "WordPress post created but required metadata failed.", "article_id": article_id, "errors": wp_publisher.last_errors})
        
        if not article_id:
            raise HTTPException(status_code=500, detail="Failed to publish to WordPress. Check logs.")
            
        draft_record.status = "published" if action == "publish" else "sent_as_draft"
        
        existing_history = db.query(PublishHistory).filter(
            PublishHistory.user_id == user_id,
            PublishHistory.game_name == draft_record.game_name,
            PublishHistory.provider == draft_record.provider
        ).first()
        
        if existing_history:
            existing_history.article_id = int(article_id) if str(article_id).isdigit() else 0
            existing_history.published_at = datetime.datetime.utcnow()
        else:
            new_history = PublishHistory(
                user_id=user_id,
                game_name=draft_record.game_name,
                provider=draft_record.provider,
                article_id=int(article_id) if str(article_id).isdigit() else 0
            )
            db.add(new_history)
        db.commit()
        
        log_audit_event(user_id, "POST_PUBLISHED", "ContentDraft", str(draft_id), details={"article_id": article_id})
        
        post_url = f"{site_profile['site_url']}/?p={article_id}" if site_profile['site_url'] else ""
        return {"message": f"Successfully published. WordPress Post ID: {article_id}", "post_url": post_url}

class ImageAssignmentCreate(BaseModel):
    image_id: str
    section_id: str
    template_id: Optional[str] = None
    job_id: Optional[str] = None
    draft_id: Optional[int] = None
    position: str = "after_heading"
    size: str = "medium"
    alignment: str = "center"
    custom_width: Optional[int] = None
    custom_height: Optional[int] = None
    fallback_behavior: str = "do_not_publish"

class LinkJobImagesRequest(BaseModel):
    job_id: str
    image_ids: List[str]
    dry_run: bool = False

@app.post("/api/links")
async def add_link(
    url: str = Form(...),
    game_name: str = Form(""),
    provider: str = Form(""),
    market: str = Form("UK"),
    featured_image: UploadFile = File(None),
    description_image: UploadFile = File(None),
    user_id: int = Depends(get_current_user_id)
):
    try:
        if not check_user_quota(user_id):
            raise HTTPException(status_code=402, detail="Monthly article limit reached for your subscription plan.")
            
        temp_dir = os.path.join(DATA_DIR, 'tmp_uploads')
        os.makedirs(temp_dir, exist_ok=True)
        
        def process_upload(upload_file: UploadFile):
            if not upload_file or not upload_file.filename:
                return None
            ext = os.path.splitext(upload_file.filename)[1].lower()
            if ext not in ['.jpg', '.jpeg', '.png', '.webp']:
                return None
            safe_filename = f"{uuid.uuid4().hex}{ext}"
            temp_path = os.path.join(temp_dir, safe_filename)
            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(upload_file.file, buffer)
            return temp_path

        featured_url = process_upload(featured_image) if featured_image else None
        desc_url = process_upload(description_image) if description_image else None
        configured_settings = get_user_settings(user_id) or {}
        with SessionLocal() as db:
            configured_site = db.query(WordPressSite).filter(
                WordPressSite.user_id == user_id,
                WordPressSite.site_url == configured_settings.get("wp_url")
            ).first()
            selected_site_id = configured_site.id if configured_site else None
        
        with get_db_connection() as conn:
            conn.execute("""
                INSERT INTO links (user_id, url, game_name, provider, featured_image, description_image, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, url, game_name or "Extracting...", provider or "Extracting...", featured_url, desc_url, 'New'))
            conn.commit()
            
        # Automatically enqueue job for the submitted link
        job_id = f"job-{uuid.uuid4().hex[:12]}"
        now = datetime.datetime.utcnow()
        
        with SessionLocal() as db:
            new_job = Job(
                id=job_id,
                user_id=user_id,
                site_id=selected_site_id,
                game_name=game_name or "Pending Extraction",
                provider=provider or "Pending Extraction",
                target_market=market,
                status="QUEUED",
                current_stage="QUEUED",
                created_at=now
            )
            db.add(new_job)
            db.add(JobEvent(job_id=job_id, user_id=user_id, event_type="JOB_CREATED", stage="QUEUED", status="QUEUED", message=f"Queued URL: {url}"))
            db.add(JobEvent(job_id=job_id, user_id=user_id, event_type="JOB_QUEUED", stage="QUEUED", status="QUEUED", message="Enqueued into Redis worker queue."))
            
            # Associate any orphaned image assignments with this new job
            from utils.db_models import ImageAssignment
            orphaned_assignments = db.query(ImageAssignment).filter(
                ImageAssignment.user_id == user_id,
                ImageAssignment.job_id.is_(None),
                ImageAssignment.draft_id.is_(None)
            ).all()
            for assignment in orphaned_assignments:
                assignment.job_id = job_id
            
            db.commit()
            
        payload = {
            "job_id": job_id,
            "user_id": user_id,
            "url": url,
            "game_name": game_name,
            "provider": provider,
            "target_market": market,
            "featured_image_url": featured_url,
            "description_image_url": desc_url,
            "site_id": selected_site_id,
            "dry_run": False
        }
        if not enqueue_job(job_id, payload):
            with SessionLocal() as db:
                job_record = db.query(Job).filter(Job.id == job_id).first()
                if job_record:
                    job_record.status = "FAILED"
                    job_record.current_stage = "QUEUE"
                    job_record.error_message = "Job queue is unavailable. Configure Redis before retrying."
                    job_record.failed_at = datetime.datetime.utcnow()
                    db.commit()
            raise HTTPException(status_code=503, detail="Job queue is unavailable. Please configure Redis and retry.")
        log_audit_event(user_id, "URL_LINK_QUEUED", "Link", job_id, details={"url": url})
        
        return {"message": "Target URL queued and automation job enqueued successfully!", "job_id": job_id}
    except HTTPException:
        raise
    except Exception as e:
        request_id = uuid.uuid4().hex[:12]
        logger.exception("Failed to queue link %s for user %s", request_id, user_id)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Failed to queue link. Please retry or contact support.",
                "request_id": request_id,
            }
        )

@app.get("/api/links/status")
def get_links_status(user_id: int = Depends(get_current_user_id)):
    with get_db_connection() as conn:
        result = conn.execute("SELECT id, url, game_name, provider, status, status_reason, created_at FROM links WHERE user_id = ? ORDER BY created_at DESC LIMIT 50", (user_id,))
        rows = result.fetchall()
        return [dict(row) for row in rows]

@app.get("/api/logs")
def get_logs(user_id: int = Depends(get_current_user_id)):
    log_file = os.path.join(DATA_DIR, 'orchestrator.log')
    if not os.path.exists(log_file):
        return {"logs": []}
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        return {"logs": lines[-100:]}
    except Exception as e:
        return {"error": str(e)}

# --- ADMIN DASHBOARD & MONITORING APIS ---

@app.get("/api/admin/users")
def admin_get_users(admin_id: int = Depends(require_admin)):
    with SessionLocal() as db:
        users = db.query(User).all()
        result = []
        for u in users:
            sub = db.query(Subscription).filter(Subscription.user_id == u.id).first()
            result.append({
                "id": u.id,
                "email": u.email,
                "role": u.role,
                "plan": sub.plan if sub else "free",
                "article_limit": sub.article_limit if sub else 5,
                "monthly_usage": sub.monthly_usage if sub else 0,
                "is_active": u.is_active,
                "created_at": u.created_at.strftime("%Y-%m-%d") if u.created_at else None
            })
        return result

class AdminUserUpdate(BaseModel):
    role: str
    plan: str
    article_limit: int

@app.put("/api/admin/users/{user_id}")
def admin_update_user(user_id: int, payload: AdminUserUpdate, admin_id: int = Depends(require_admin)):
    with SessionLocal() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user.role = payload.role
        
        sub = db.query(Subscription).filter(Subscription.user_id == user_id).first()
        if sub:
            sub.plan = payload.plan
            sub.article_limit = payload.article_limit
        else:
            new_sub = Subscription(user_id=user_id, plan=payload.plan, article_limit=payload.article_limit)
            db.add(new_sub)
            
        db.commit()
        return {"status": "success"}

@app.get("/api/admin/stats")
def get_admin_stats(admin = Depends(require_admin)):
    with SessionLocal() as db:
        total_users = db.query(User).count()
        total_jobs = db.query(Job).count()
        queued_jobs = db.query(Job).filter(Job.status == "QUEUED").count()
        processing_jobs = db.query(Job).filter(Job.status == "PROCESSING").count()
        completed_jobs = db.query(Job).filter(Job.status.in_(["PENDING_REVIEW", "PUBLISHED"])).count()
        failed_jobs = db.query(Job).filter(Job.status == "FAILED").count()
        
        success_rate = (completed_jobs / total_jobs * 100.0) if total_jobs > 0 else 100.0
        
        return {
            "total_users": total_users,
            "total_jobs": total_jobs,
            "queued_jobs": queued_jobs,
            "processing_jobs": processing_jobs,
            "completed_jobs": completed_jobs,
            "failed_jobs": failed_jobs,
            "success_rate": round(success_rate, 1)
        }

@app.get("/api/admin/workers")
def get_admin_workers(admin = Depends(require_admin)):
    now = datetime.datetime.utcnow()
    timeout_threshold = now - datetime.timedelta(seconds=45)
    offline_threshold = now - datetime.timedelta(seconds=120)
    
    with SessionLocal() as db:
        workers = db.query(Worker).all()
        result = []
        for w in workers:
            health = "HEALTHY"
            if w.last_heartbeat < offline_threshold:
                health = "OFFLINE"
            elif w.last_heartbeat < timeout_threshold:
                health = "STALE"
                
            result.append({
                "id": w.id,
                "name": w.worker_name,
                "hostname": w.hostname,
                "pid": w.process_id,
                "status": w.status,
                "health": health,
                "current_job_id": w.current_job_id,
                "current_stage": w.current_stage,
                "jobs_completed": w.jobs_completed,
                "jobs_failed": w.jobs_failed,
                "last_heartbeat": w.last_heartbeat.strftime("%H:%M:%S") if w.last_heartbeat else None
            })
        return result

@app.get("/api/admin/jobs")
def get_admin_jobs(admin = Depends(require_admin)):
    with SessionLocal() as db:
        jobs = db.query(Job).order_by(Job.created_at.desc()).limit(100).all()
        return [
            {
                "job_id": j.id,
                "user_id": j.user_id,
                "game_name": j.game_name,
                "provider": j.provider,
                "status": j.status,
                "current_stage": j.current_stage,
                "worker_id": j.worker_id,
                "retry_count": j.retry_count,
                "duration": j.duration,
                "created_at": j.created_at.strftime("%Y-%m-%d %H:%M:%S") if j.created_at else None
            }
            for j in jobs
        ]

@app.get("/api/admin/errors")
def get_admin_errors(admin = Depends(require_admin)):
    with SessionLocal() as db:
        errors = db.query(SystemErrorLog).order_by(SystemErrorLog.created_at.desc()).limit(50).all()
        return [
            {
                "id": e.id,
                "user_id": e.user_id,
                "job_id": e.job_id,
                "category": e.category,
                "error_code": e.error_code,
                "message": e.message,
                "timestamp": e.created_at.strftime("%Y-%m-%d %H:%M:%S") if e.created_at else None
            }
            for e in errors
        ]

@app.get("/api/admin/audit-logs")
def get_admin_audit_logs(admin = Depends(require_admin)):
    with SessionLocal() as db:
        logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(100).all()
        return [
            {
                "id": a.id,
                "user_id": a.user_id,
                "action": a.action,
                "resource_type": a.resource_type,
                "resource_id": a.resource_id,
                "ip_address": a.ip_address,
                "timestamp": a.created_at.strftime("%Y-%m-%d %H:%M:%S") if a.created_at else None
            }
            for a in logs
        ]

@app.get("/api/admin/pipeline")
def get_admin_pipeline(admin = Depends(require_admin)):
    """
    Returns live workflow statistics across pipeline stages.
    EXPLICITLY INCLUDES FAKE-FACT MAKER STAGE (FACT_PROCESSING).
    """
    stages = [
        "QUEUED", "DISCOVERY", "RESEARCH", "FACT_PROCESSING",
        "CONTENT_GENERATION", "IMAGE_PROCESSING", "QUALITY_CHECK",
        "PENDING_REVIEW", "WORDPRESS_PUBLISH", "COMPLETED"
    ]
    with SessionLocal() as db:
        counts = {}
        for s in stages:
            c = db.query(Job).filter(Job.current_stage == s).count()
            counts[s] = c
        return {"pipeline_stages": counts}

@app.get("/api/admin/analytics")
def get_admin_analytics(admin = Depends(require_admin)):
    with SessionLocal() as db:
        total_usage = db.query(UsageRecord).count()
        total_cost = db.query(CostRecord).all()
        cost_sum = sum(c.amount for c in total_cost)
        return {
            "total_ai_requests": total_usage,
            "estimated_operational_cost": round(cost_sum, 2),
            "estimated_gross_margin": "84.5%"
        }

@app.get("/api/health")
def health_check():
    redis_ok = is_redis_available()
    with SessionLocal() as db:
        active_workers = db.query(Worker).filter(Worker.status.in_(["IDLE", "BUSY"])).count()
    return {
        "status": "healthy",
        "database": "connected",
        "redis_queue": "connected" if redis_ok else "local_fallback",
        "active_workers": active_workers,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }

# --- TEMPLATES & SECTIONS APIS ---

@app.get("/api/templates")
def get_templates_endpoint(user_id: int = Depends(get_current_user_id)):
    from services.template_service import get_user_templates
    return get_user_templates(user_id)

@app.get("/api/templates/{template_id}")
def get_template_detail_endpoint(template_id: int, user_id: int = Depends(get_current_user_id)):
    from services.template_service import get_template_by_id
    tmpl = get_template_by_id(template_id, user_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return tmpl

@app.post("/api/templates")
def create_template_endpoint(payload: ContentTemplateCreate, user_id: int = Depends(get_current_user_id)):
    from services.template_service import create_custom_template
    tmpl = create_custom_template(user_id, payload)
    log_audit_event(user_id, "TEMPLATE_CREATED", "ContentTemplate", str(tmpl.id))
    return {"message": "Template created successfully", "template_id": tmpl.id}

@app.post("/api/templates/{template_id}/duplicate")
def duplicate_template_endpoint(template_id: int, user_id: int = Depends(get_current_user_id)):
    from services.template_service import duplicate_template
    dup = duplicate_template(template_id, user_id)
    if not dup:
        raise HTTPException(status_code=404, detail="Template not found")
    log_audit_event(user_id, "TEMPLATE_DUPLICATED", "ContentTemplate", str(dup.id))
    return {"message": "Template duplicated successfully", "template_id": dup.id}

@app.post("/api/templates/{template_id}/set-default")
def set_template_default_endpoint(template_id: int, user_id: int = Depends(get_current_user_id)):
    from services.template_service import set_template_default
    success = set_template_default(template_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Template not found")
    log_audit_event(user_id, "TEMPLATE_SET_DEFAULT", "ContentTemplate", str(template_id))
    return {"message": "Template set as default"}

@app.delete("/api/templates/{template_id}")
def delete_template_endpoint(template_id: int, user_id: int = Depends(get_current_user_id)):
    from services.template_service import delete_template
    success = delete_template(template_id, user_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot delete default or missing template")
    log_audit_event(user_id, "TEMPLATE_DELETED", "ContentTemplate", str(template_id))
    return {"message": "Template deleted"}

# --- IMAGE ASSETS & ASSIGNMENTS APIS ---

@app.post("/api/images/upload")
async def upload_image_asset(
    file: UploadFile = File(...),
    target_width: Optional[int] = Form(None),
    target_height: Optional[int] = Form(None),
    user_id: int = Depends(get_current_user_id)
):
    try:
        from agents.image_agent import ImageAgent
        img_agent = ImageAgent()
        
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ['.jpg', '.jpeg', '.png', '.webp']:
            raise HTTPException(status_code=400, detail="Unsupported image format. Allowed: JPG, PNG, WEBP.")
            
        image_id = f"img-{uuid.uuid4().hex[:12]}"
        safe_filename = f"{image_id}{ext}"
        upload_dir = os.path.join(DATA_DIR, 'images')
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, safe_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Pillow processing
        info = img_agent.process_custom_image(file_path, target_width=target_width, target_height=target_height)
        
        with SessionLocal() as db:
            asset = ImageAsset(
                id=image_id,
                user_id=user_id,
                filename=file.filename,
                file_path=file_path,
                mime_type=f"image/{ext.replace('.', '')}",
                width=info["width"],
                height=info["height"],
                file_size=info["file_size"]
            )
            db.add(asset)
            db.commit()
            
        log_audit_event(user_id, "IMAGE_UPLOADED", "ImageAsset", image_id)
        return {
            "message": "Image uploaded and processed via Pillow",
            "image_id": image_id,
            "url": f"/api/images/{image_id}/file",
            "width": info["width"],
            "height": info["height"]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/images")
def list_user_images(user_id: int = Depends(get_current_user_id)):
    with SessionLocal() as db:
        assets = db.query(ImageAsset).filter(ImageAsset.user_id == user_id).order_by(ImageAsset.created_at.desc()).all()
        return [
            {
                "id": a.id,
                "filename": a.filename,
                "url": f"/api/images/{a.id}/file",
                "width": a.width,
                "height": a.height,
                "file_size": a.file_size,
                "created_at": a.created_at.strftime("%Y-%m-%d %H:%M:%S")
            }
            for a in assets
        ]

@app.get("/api/images/{image_id}/file")
def serve_image_file(image_id: str, user_id: int = Depends(get_current_user_id)):
    from fastapi.responses import FileResponse
    with SessionLocal() as db:
        asset = db.query(ImageAsset).filter(ImageAsset.id == image_id, ImageAsset.user_id == user_id).first()
        if not asset or not os.path.exists(asset.file_path):
            raise HTTPException(status_code=404, detail="Image file not found")
        return FileResponse(asset.file_path, media_type=asset.mime_type)

@app.get("/api/images/assignments")
def get_image_assignments_endpoint(user_id: int = Depends(get_current_user_id)):
    with SessionLocal() as db:
        assignments = db.query(ImageAssignment).filter(ImageAssignment.user_id == user_id).all()
        result = []
        for a in assignments:
            asset = db.query(ImageAsset).filter(ImageAsset.id == a.image_id).first()
            sec = db.query(TemplateSection).filter(TemplateSection.id == a.section_id).first()
            result.append({
                "id": a.id,
                "image_id": a.image_id,
                "filename": asset.filename if asset else "Image",
                "url": f"/api/images/{a.image_id}/file" if asset else "",
                "section_id": a.section_id,
                "section_name": sec.name if sec else "Assigned Section",
                "position": a.position,
                "alignment": a.alignment,
                "size": a.size,
                "width": a.custom_width or (asset.width if asset else 800),
                "height": a.custom_height or (asset.height if asset else 0),
                "fallback_behavior": a.fallback_behavior
            })
        return result

@app.post("/api/images/assign")
def assign_image_to_section(payload: ImageAssignmentCreate, user_id: int = Depends(get_current_user_id)):
    with SessionLocal() as db:
        asset = db.query(ImageAsset).filter(ImageAsset.id == payload.image_id, ImageAsset.user_id == user_id).first()
        if not asset:
            raise HTTPException(status_code=404, detail="Image asset not found")

        if payload.template_id is not None:
            try:
                template_id = int(payload.template_id)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="Invalid template ID")
            template = db.query(ContentTemplate).filter(
                ContentTemplate.id == template_id, ContentTemplate.user_id == user_id
            ).first()
            if not template:
                raise HTTPException(status_code=404, detail="Template not found")
            if not db.query(TemplateSection).filter(
                TemplateSection.id == payload.section_id, TemplateSection.template_id == template_id
            ).first():
                raise HTTPException(status_code=404, detail="Template section not found")

        if payload.job_id is not None and not db.query(Job).filter(
            Job.id == payload.job_id, Job.user_id == user_id
        ).first():
            raise HTTPException(status_code=404, detail="Job not found")
        if payload.draft_id is not None and not db.query(ContentDraft).filter(
            ContentDraft.id == payload.draft_id, ContentDraft.user_id == user_id
        ).first():
            raise HTTPException(status_code=404, detail="Draft not found")
            
        assignment = db.query(ImageAssignment).filter(
            ImageAssignment.user_id == user_id,
            ImageAssignment.image_id == payload.image_id,
            ImageAssignment.section_id == payload.section_id
        ).first()
        
        if not assignment:
            assignment = ImageAssignment(
                user_id=user_id,
                image_id=payload.image_id,
                section_id=payload.section_id,
                template_id=payload.template_id,
                job_id=payload.job_id,
                draft_id=payload.draft_id,
                position=payload.position,
                alignment=payload.alignment,
                size=payload.size,
                custom_width=payload.custom_width,
                custom_height=payload.custom_height,
                fallback_behavior=payload.fallback_behavior
            )
            db.add(assignment)
        else:
            assignment.position = payload.position
            assignment.alignment = payload.alignment
            assignment.size = payload.size
            assignment.custom_width = payload.custom_width
            assignment.custom_height = payload.custom_height
            assignment.fallback_behavior = payload.fallback_behavior
            
        db.commit()
        log_audit_event(user_id, "IMAGE_ASSIGNED", "ImageAssignment", str(assignment.id), details={"section_id": payload.section_id})
        return {"message": "Image assignment saved", "assignment_id": assignment.id}

# --- LINK UPLOADED IMAGES TO A JOB ---
@app.post("/api/images/link-job")
def link_images_to_job(payload: LinkJobImagesRequest, user_id: int = Depends(get_current_user_id)):
    with SessionLocal() as db:
        if not db.query(Job).filter(Job.id == payload.job_id, Job.user_id == user_id).first():
            raise HTTPException(status_code=404, detail="Job not found")
        for img_id in payload.image_ids:
            assignment = db.query(ImageAssignment).filter(
                ImageAssignment.user_id == user_id,
                ImageAssignment.image_id == str(img_id)
            ).first()
            if assignment:
                assignment.job_id = payload.job_id
        db.commit()
    return {"status": "ok", "job_id": payload.job_id}

# --- VALIDATION & PREVIEW APIS ---

class ContentPreviewRequest(BaseModel):
    draft_id: Optional[int] = None
    document: Optional[Dict[str, Any]] = None
    template_id: Optional[int] = None

@app.post("/api/content/validate")
def validate_content_endpoint(req: ContentPreviewRequest, user_id: int = Depends(get_current_user_id)):
    from core.universal_model import ContentDocument
    from services.validation_service import validate_content_before_publish
    
    doc = None
    with SessionLocal() as db:
        if req.draft_id:
            d = db.query(ContentDraft).filter(ContentDraft.id == req.draft_id, ContentDraft.user_id == user_id).first()
            if d and d.document_json:
                doc = ContentDocument(**json.loads(d.document_json))
        elif req.document:
            doc = ContentDocument(**req.document)
            
    if not doc:
        raise HTTPException(status_code=400, detail="Invalid document payload for validation")
        
    res = validate_content_before_publish(doc, user_id, template_id=req.template_id)
    return res

@app.post("/api/content/preview")
def preview_content_endpoint(req: ContentPreviewRequest, user_id: int = Depends(get_current_user_id)):
    from core.universal_model import ContentDocument
    from core.rendering_engine import RenderingEngine
    
    doc = None
    with SessionLocal() as db:
        if req.draft_id:
            d = db.query(ContentDraft).filter(ContentDraft.id == req.draft_id, ContentDraft.user_id == user_id).first()
            if d and d.document_json:
                doc = ContentDocument(**json.loads(d.document_json))
        elif req.document:
            doc = ContentDocument(**req.document)
            
    if not doc:
        raise HTTPException(status_code=400, detail="Invalid document payload for preview")

    # Fetch image assignments for user
    with SessionLocal() as db:
        assignments = db.query(ImageAssignment).filter(ImageAssignment.user_id == user_id).all()
        assign_dicts = []
        for a in assignments:
            asset = db.query(ImageAsset).filter(ImageAsset.id == a.image_id).first()
            if asset:
                assign_dicts.append({
                    "url": f"/api/images/{asset.id}/file",
                    "section_id": a.section_id,
                    "position": a.position,
                    "alignment": a.alignment,
                    "size": a.size,
                    "width": a.custom_width or asset.width,
                    "height": a.custom_height or asset.height,
                    "fallback_behavior": a.fallback_behavior
                })

    rendered_html = RenderingEngine.render_classic_html(doc, image_assignments=assign_dicts)
    return {"title": doc.title, "html_preview": rendered_html}

# --- ENHANCED HISTORY PANEL APIS ---

@app.get("/api/history")
def get_enhanced_history(
    q: Optional[str] = None,
    status: Optional[str] = None,
    template_id: Optional[int] = None,
    user_id: int = Depends(get_current_user_id)
):
    with SessionLocal() as db:
        query = db.query(PublishHistory).filter(PublishHistory.user_id == user_id)
        if q:
            query = query.filter(PublishHistory.game_name.ilike(f"%{q}%"))
        history = query.order_by(PublishHistory.published_at.desc()).limit(100).all()
        
        return [
            {
                "id": h.id,
                "game_name": h.game_name,
                "provider": h.provider,
                "article_id": h.article_id,
                "status": "Published" if h.article_id else "Failed",
                "published_at": h.published_at.strftime("%Y-%m-%d %H:%M:%S") if h.published_at else None
            }
            for h in history
        ]

@app.delete("/api/history/{history_id}")
def delete_single_history(history_id: int, user_id: int = Depends(get_current_user_id)):
    with SessionLocal() as db:
        h = db.query(PublishHistory).filter(PublishHistory.id == history_id, PublishHistory.user_id == user_id).first()
        if not h:
            raise HTTPException(status_code=404, detail="History entry not found")
        db.delete(h)
        db.commit()
    log_audit_event(user_id, "HISTORY_DELETED", "PublishHistory", str(history_id))
    return {"message": "History entry deleted"}

@app.post("/api/history/bulk-delete")
def bulk_delete_history(history_ids: Optional[List[int]] = None, delete_all: bool = False, user_id: int = Depends(get_current_user_id)):
    with SessionLocal() as db:
        if delete_all:
            db.query(PublishHistory).filter(PublishHistory.user_id == user_id).delete()
        elif history_ids:
            db.query(PublishHistory).filter(PublishHistory.user_id == user_id, PublishHistory.id.in_(history_ids)).delete(synchronize_session=False)
        db.commit()
    log_audit_event(user_id, "HISTORY_BULK_DELETED", "PublishHistory", "bulk")
    return {"message": "Selected history entries deleted"}

@app.post("/api/history/{history_id}/retry")
def retry_history_job(history_id: int, user_id: int = Depends(get_current_user_id)):
    with SessionLocal() as db:
        h = db.query(PublishHistory).filter(PublishHistory.id == history_id, PublishHistory.user_id == user_id).first()
        if not h:
            raise HTTPException(status_code=404, detail="History entry not found")
        
        job_id = f"job-retry-{uuid.uuid4().hex[:8]}"
        new_job = Job(
            id=job_id,
            user_id=user_id,
            game_name=h.game_name,
            provider=h.provider,
            status="QUEUED",
            current_stage="QUEUED"
        )
        db.add(new_job)
        db.commit()
        
    enqueue_job(job_id, {"job_id": job_id, "user_id": user_id, "game_name": h.game_name, "provider": h.provider, "dry_run": False})
    log_audit_event(user_id, "HISTORY_RETRIED", "Job", job_id)
    return {"message": "Job retry enqueued", "job_id": job_id}
