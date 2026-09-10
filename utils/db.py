import sqlite3
import os
import re
from contextlib import contextmanager
from sqlalchemy import text
from utils.logger import get_logger

logger = get_logger("db_utils")

# Railway's application filesystem may be read-only. Use /tmp in production unless
# an external/persistent DATA_DIR has been configured explicitly.
_default_data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
if (
    os.environ.get('APP_ENV', 'development').strip().lower() in {'production', 'prod'}
    or os.environ.get('RAILWAY_ENVIRONMENT')
):
    _default_data_dir = os.path.join('/tmp', 'seo_automation')
DATA_DIR = os.environ.get('DATA_DIR', _default_data_dir)
os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, 'history.db')
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'schema.sql')
DATABASE_URL = os.getenv("DATABASE_URL", "")
USE_POSTGRES = DATABASE_URL.startswith(("postgresql://", "postgres://"))


class _SQLAlchemyCursor:
    def __init__(self, result):
        self._result = result

    def fetchone(self):
        return self._result.mappings().fetchone()

    def fetchall(self):
        return self._result.mappings().fetchall()


class _SQLAlchemyConnection:
    def __init__(self, connection):
        self._connection = connection

    @staticmethod
    def _statement(sql, parameters):
        if not parameters:
            return text(sql), {}
        values = iter(parameters)
        named_parameters = {}

        def replace_parameter(_match):
            name = f"param_{len(named_parameters)}"
            named_parameters[name] = next(values)
            return f":{name}"

        return text(re.sub(r"\?", replace_parameter, sql)), named_parameters

    def execute(self, sql, parameters=()):
        statement, values = self._statement(sql, parameters)
        return _SQLAlchemyCursor(self._connection.execute(statement, values))

    def commit(self):
        self._connection.commit()

    def close(self):
        self._connection.close()

@contextmanager
def get_db_connection(db_path=None):
    # Explicit paths are used by local tests and isolated agent operations.
    use_postgres = USE_POSTGRES and db_path in (None, DB_PATH)
    if use_postgres:
        from utils.db_models import engine

        connection = _SQLAlchemyConnection(engine.connect())
        try:
            yield connection
        except Exception:
            connection._connection.rollback()
            raise
        else:
            connection.commit()
        finally:
            connection.close()
        return

    db_path = db_path or DB_PATH
    conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES, timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        yield conn
    finally:
        conn.close()

def init_db(db_path=DB_PATH, schema_path=SCHEMA_PATH):
    """Initialize the SQLite database with the schema and auto-migrate new columns."""
    if USE_POSTGRES and db_path == DB_PATH:
        from utils.db_models import engine
        schema_file = os.path.join(os.path.dirname(schema_path), "schema.supabase.sql")
        if os.path.exists(schema_file):
            with open(schema_file, encoding="utf-8") as file:
                statements = [statement.strip() for statement in file.read().split(";") if statement.strip()]
            with engine.begin() as connection:
                for statement in statements:
                    connection.execute(text(statement))
        logger.info("Using DATABASE_URL database; SQLAlchemy and raw schema tables initialized.")
        return

    with get_db_connection(db_path) as conn:
        if os.path.exists(schema_path):
            with open(schema_path, 'r') as f:
                conn.executescript(f.read())
        
        # Migration: Ensure users table has role, subscription_plan, is_active
        cursor = conn.execute("PRAGMA table_info(users)")
        cols = [row['name'] for row in cursor.fetchall()]
        if 'role' not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
        if 'subscription_plan' not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN subscription_plan TEXT DEFAULT 'free'")
        if 'is_active' not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1")

        # Migration: Ensure user_settings table has active_format_mode and active_template_id
        cursor = conn.execute("PRAGMA table_info(user_settings)")
        us_cols = [row['name'] for row in cursor.fetchall()]
        if 'active_format_mode' not in us_cols:
            conn.execute("ALTER TABLE user_settings ADD COLUMN active_format_mode TEXT DEFAULT 'default'")
        if 'active_template_id' not in us_cols:
            conn.execute("ALTER TABLE user_settings ADD COLUMN active_template_id INTEGER DEFAULT NULL")
        if 'default_market' not in us_cols:
            conn.execute("ALTER TABLE user_settings ADD COLUMN default_market TEXT DEFAULT 'UK'")
        if 'default_word_count' not in us_cols:
            conn.execute("ALTER TABLE user_settings ADD COLUMN default_word_count TEXT DEFAULT '1500'")
        if 'default_tone' not in us_cols:
            conn.execute("ALTER TABLE user_settings ADD COLUMN default_tone TEXT DEFAULT 'professional'")
        if 'default_keyword_density' not in us_cols:
            conn.execute("ALTER TABLE user_settings ADD COLUMN default_keyword_density TEXT DEFAULT '1.2'")
        if 'airtable_api_key' not in us_cols:
            conn.execute("ALTER TABLE user_settings ADD COLUMN airtable_api_key TEXT DEFAULT NULL")
        if 'airtable_base_id' not in us_cols:
            conn.execute("ALTER TABLE user_settings ADD COLUMN airtable_base_id TEXT DEFAULT NULL")
        if 'airtable_table_name' not in us_cols:
            conn.execute("ALTER TABLE user_settings ADD COLUMN airtable_table_name TEXT DEFAULT 'Links'")
        if 'theme_type' not in us_cols:
            conn.execute("ALTER TABLE user_settings ADD COLUMN theme_type TEXT DEFAULT 'standard'")
        if 'seo_plugin' not in us_cols:
            conn.execute("ALTER TABLE user_settings ADD COLUMN seo_plugin TEXT DEFAULT 'none'")

        # Compatibility migration for older trusted_facts tables created before user_id defaulting was enforced.
        cursor = conn.execute("PRAGMA table_info(trusted_facts)")
        fact_cols = [row['name'] for row in cursor.fetchall()]
        if 'user_id' not in fact_cols:
            conn.execute("ALTER TABLE trusted_facts ADD COLUMN user_id INTEGER DEFAULT 1")
        conn.execute("UPDATE trusted_facts SET user_id = 1 WHERE user_id IS NULL")

        conn.commit()
    logger.info("Database initialized with column migrations.")
