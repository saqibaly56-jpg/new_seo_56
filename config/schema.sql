CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER PRIMARY KEY,
    wp_url TEXT,
    wp_username TEXT,
    wp_app_password TEXT,
    theme_type TEXT DEFAULT 'standard',
    seo_plugin TEXT DEFAULT 'none',
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    url TEXT NOT NULL,
    game_name TEXT,
    provider TEXT,
    status TEXT DEFAULT 'New',
    status_reason TEXT,
    featured_image TEXT,
    description_image TEXT,
    login_image TEXT,
    transaction_image TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS publish_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    game_name TEXT NOT NULL,
    provider TEXT NOT NULL,
    article_id TEXT,
    published_at TIMESTAMP NOT NULL,
    UNIQUE(user_id, game_name, provider),
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS trusted_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL DEFAULT 1,
    game_name TEXT NOT NULL,
    provider TEXT NOT NULL,
    rtp REAL,
    volatility TEXT,
    max_win TEXT,
    release_date TEXT,
    min_bet REAL,
    max_bet REAL,
    UNIQUE(user_id, game_name, provider),
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS image_licenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    game_name TEXT NOT NULL,
    provider TEXT NOT NULL,
    file_path TEXT NOT NULL,
    license_type TEXT NOT NULL,
    license_notes TEXT,
    UNIQUE(user_id, game_name, provider),
    FOREIGN KEY(user_id) REFERENCES users(id)
);
