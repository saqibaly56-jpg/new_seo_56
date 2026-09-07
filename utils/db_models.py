from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, Text, create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import datetime
import os

DATA_DIR = os.getenv("DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data'))
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(DATA_DIR, 'history.db')}")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="user", nullable=False) # "user" or "admin"
    subscription_plan = Column(String, default="free", nullable=False) # "free", "starter", "pro", "business"
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    settings = relationship("UserSettings", back_populates="user", uselist=False)
    history = relationship("PublishHistory", back_populates="user")
    wp_sites = relationship("WordPressSite", back_populates="user")
    drafts = relationship("ContentDraft", back_populates="user")
    jobs = relationship("Job", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")
    subscription = relationship("Subscription", back_populates="user", uselist=False)

class WordPressSite(Base):
    __tablename__ = "wordpress_sites"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    
    # Credentials
    site_url = Column(String, index=True)
    username = Column(String)
    app_password = Column(String)
    
    # Profile / Discovery Data
    active_theme = Column(String, default="unknown")
    editor_type = Column(String, default="classic")
    seo_plugin = Column(String, default="none")
    capabilities = Column(Text, default="{}")
    category_mapping = Column(Text, default="{}")
    
    status = Column(String, default="connected")
    last_connected_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    user = relationship("User", back_populates="wp_sites")

class UserSettings(Base):
    __tablename__ = "user_settings"
    
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True, unique=True, index=True)
    
    wp_url = Column(String, nullable=True)
    wp_username = Column(String, nullable=True)
    wp_app_password = Column(String, nullable=True)
    
    airtable_api_key = Column(String, nullable=True)
    airtable_base_id = Column(String, nullable=True)
    airtable_table_name = Column(String, default="Links")
    
    theme_type = Column(String, default="standard")
    seo_plugin = Column(String, default="none")
    
    active_format_mode = Column(String, default="default") # "default" or "custom"
    active_template_id = Column(Integer, nullable=True)
    
    default_market = Column(String, default="UK")
    default_word_count = Column(String, default="1500")
    default_tone = Column(String, default="professional")
    default_keyword_density = Column(String, default="1.2")
    
    user = relationship("User", back_populates="settings")

class ContentDraft(Base):
    __tablename__ = "content_drafts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    site_id = Column(Integer, ForeignKey("wordpress_sites.id"), nullable=True)
    job_id = Column(String, nullable=True, index=True)
    
    game_name = Column(String, index=True)
    provider = Column(String, index=True)
    document_json = Column(Text) 
    
    status = Column(String, default="draft", index=True) # draft, approved, published, failed
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    
    user = relationship("User", back_populates="drafts")

class PublishHistory(Base):
    __tablename__ = "publish_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    
    game_name = Column(String, index=True)
    provider = Column(String, index=True)
    article_id = Column(Integer, nullable=True)
    published_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    
    user = relationship("User", back_populates="history")

class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(String, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    site_id = Column(Integer, ForeignKey("wordpress_sites.id"), nullable=True)
    
    game_name = Column(String, index=True)
    provider = Column(String, index=True)
    target_market = Column(String, default="UK")
    
    # State machine: QUEUED, PROCESSING, PENDING_REVIEW, PUBLISHED, FAILED, RETRYING, CANCELLED
    status = Column(String, default="QUEUED", index=True, nullable=False)
    current_stage = Column(String, default="QUEUED", index=True)
    worker_id = Column(String, nullable=True, index=True)
    
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    error_message = Column(Text, nullable=True)
    duration = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="jobs")

class JobEvent(Base):
    __tablename__ = "job_events"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, ForeignKey("jobs.id"), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    
    event_type = Column(String, index=True, nullable=False)
    stage = Column(String, index=True, nullable=False)
    status = Column(String, index=True, nullable=False)
    message = Column(Text, nullable=True)
    worker_id = Column(String, nullable=True)
    metadata_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)

class Worker(Base):
    __tablename__ = "workers"
    
    id = Column(String, primary_key=True, index=True)
    worker_name = Column(String, index=True, nullable=False)
    hostname = Column(String)
    process_id = Column(Integer)
    
    # STARTING, IDLE, BUSY, STOPPING, OFFLINE, ERROR
    status = Column(String, default="STARTING", index=True, nullable=False)
    current_job_id = Column(String, nullable=True, index=True)
    current_stage = Column(String, nullable=True)
    
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_heartbeat = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    jobs_completed = Column(Integer, default=0)
    jobs_failed = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    
    action = Column(String, index=True, nullable=False)
    resource_type = Column(String, index=True)
    resource_id = Column(String, index=True)
    ip_address = Column(String, nullable=True)
    details_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    
    user = relationship("User", back_populates="audit_logs")

class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, index=True, nullable=False)
    
    plan = Column(String, default="free", index=True, nullable=False) # free, starter, pro, business
    status = Column(String, default="active", index=True, nullable=False)
    article_limit = Column(Integer, default=5)
    monthly_usage = Column(Integer, default=0)
    
    start_date = Column(DateTime, default=datetime.datetime.utcnow)
    renewal_date = Column(DateTime, default=datetime.datetime.utcnow)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    user = relationship("User", back_populates="subscription")

class UsageRecord(Base):
    __tablename__ = "usage_records"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    job_id = Column(String, nullable=True, index=True)
    
    event_type = Column(String, index=True, nullable=False) # ai_generation, wp_publish, image_process
    units = Column(Integer, default=1)
    tokens_used = Column(Integer, default=0)
    estimated_cost = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)

class SystemErrorLog(Base):
    __tablename__ = "system_error_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    job_id = Column(String, nullable=True, index=True)
    
    category = Column(String, index=True, nullable=False) # Auth, Redis, Worker, Groq, WordPress, Cloudflare, Network
    error_code = Column(String, index=True)
    message = Column(Text, nullable=False)
    stack_trace = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)

class CostRecord(Base):
    __tablename__ = "cost_records"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    job_id = Column(String, nullable=True, index=True)
    
    category = Column(String, index=True) # groq_llm, image_storage, server_infra
    amount = Column(Float, default=0.0)
    description = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)

class ContentTemplate(Base):
    __tablename__ = "content_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    mode = Column(String, default="custom", nullable=False) # "default" or "custom"
    is_default = Column(Boolean, default=False, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    sections = relationship("TemplateSection", back_populates="template", cascade="all, delete-orphan", order_by="TemplateSection.order")

class TemplateSection(Base):
    __tablename__ = "template_sections"
    
    id = Column(String, primary_key=True, index=True) # UUID section_id
    template_id = Column(Integer, ForeignKey("content_templates.id"), index=True, nullable=False)
    name = Column(String, nullable=False)
    order = Column(Integer, default=1, nullable=False)
    required = Column(Boolean, default=True, nullable=False)
    content_type = Column(String, default="paragraph", nullable=False) # paragraph, bullet_list, table, faq, how_to
    ai_instruction = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    template = relationship("ContentTemplate", back_populates="sections")

class ImageAsset(Base):
    __tablename__ = "image_assets"
    
    id = Column(String, primary_key=True, index=True) # UUID image_id
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    mime_type = Column(String, default="image/png")
    width = Column(Integer, default=0)
    height = Column(Integer, default=0)
    file_size = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class ImageAssignment(Base):
    __tablename__ = "image_assignments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    image_id = Column(String, ForeignKey("image_assets.id"), index=True, nullable=False)
    section_id = Column(String, index=True, nullable=False) # References TemplateSection.id UUID
    template_id = Column(Integer, ForeignKey("content_templates.id"), nullable=True)
    job_id = Column(String, nullable=True, index=True)
    draft_id = Column(Integer, nullable=True, index=True)
    
    position = Column(String, default="after_heading") # before_heading, after_heading, before_paragraph, after_paragraph, between_paragraphs, end_of_section
    alignment = Column(String, default="center") # left, center, right, full_width
    size = Column(String, default="large") # small, medium, large, full_width, custom
    custom_width = Column(Integer, nullable=True)
    custom_height = Column(Integer, nullable=True)
    fallback_behavior = Column(String, default="do_not_publish") # do_not_publish, nearest_section, end_of_article
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class WebsiteProfile(Base):
    __tablename__ = "website_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    name = Column(String, nullable=False)
    site_url = Column(String, nullable=False)
    username = Column(String, nullable=False)
    app_password = Column(String, nullable=False) # Encrypted
    default_template_id = Column(Integer, ForeignKey("content_templates.id"), nullable=True)
    editor_type = Column(String, default="classic")
    seo_plugin = Column(String, default="none")
    default_categories = Column(Text, default="[]")
    default_tags = Column(Text, default="[]")
    default_author = Column(String, nullable=True)
    image_defaults_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

# Create tables automatically
Base.metadata.create_all(bind=engine)


def _migrate_existing_schema():
    """Add model columns that create_all() cannot add to existing databases."""
    if not inspect(engine).has_table("users"):
        return

    with engine.begin() as connection:
        existing_columns = {
            column["name"] for column in inspect(connection).get_columns("users")
        }
        migrations = {
            "role": "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'",
            "subscription_plan": "ALTER TABLE users ADD COLUMN subscription_plan TEXT NOT NULL DEFAULT 'free'",
            "is_active": "ALTER TABLE users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE",
        }
        for column_name, statement in migrations.items():
            if column_name not in existing_columns:
                connection.execute(text(statement))

    if inspect(engine).has_table("user_settings"):
        user_settings_columns = {
            column["name"] for column in inspect(engine).get_columns("user_settings")
        }
        user_settings_migrations = {
            "airtable_api_key": "ALTER TABLE user_settings ADD COLUMN airtable_api_key TEXT",
            "airtable_base_id": "ALTER TABLE user_settings ADD COLUMN airtable_base_id TEXT",
            "airtable_table_name": "ALTER TABLE user_settings ADD COLUMN airtable_table_name TEXT DEFAULT 'Links'",
            "active_format_mode": "ALTER TABLE user_settings ADD COLUMN active_format_mode TEXT DEFAULT 'default'",
            "active_template_id": "ALTER TABLE user_settings ADD COLUMN active_template_id INTEGER",
            "default_market": "ALTER TABLE user_settings ADD COLUMN default_market TEXT DEFAULT 'UK'",
            "default_word_count": "ALTER TABLE user_settings ADD COLUMN default_word_count TEXT DEFAULT '1500'",
            "default_tone": "ALTER TABLE user_settings ADD COLUMN default_tone TEXT DEFAULT 'professional'",
            "default_keyword_density": "ALTER TABLE user_settings ADD COLUMN default_keyword_density TEXT DEFAULT '1.2'",
            "theme_type": "ALTER TABLE user_settings ADD COLUMN theme_type TEXT DEFAULT 'standard'",
            "seo_plugin": "ALTER TABLE user_settings ADD COLUMN seo_plugin TEXT DEFAULT 'none'",
        }
        with engine.begin() as connection:
            for column_name, statement in user_settings_migrations.items():
                if column_name not in user_settings_columns:
                    connection.execute(text(statement))


_migrate_existing_schema()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
