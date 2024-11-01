-- Messages table to store all interactions
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    channel_id TEXT NOT NULL,
    guild_id TEXT,
    user_id TEXT NOT NULL,
    persona_name TEXT,
    content TEXT NOT NULL,
    is_assistant BOOLEAN NOT NULL,
    parent_message_id INTEGER,
    emotion TEXT,
    FOREIGN KEY (parent_message_id) REFERENCES messages(id)
);

-- Context windows configuration
CREATE TABLE IF NOT EXISTS context_windows (
    channel_id TEXT PRIMARY KEY,
    window_size INTEGER NOT NULL,
    last_modified DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Image alt text storage
CREATE TABLE IF NOT EXISTS image_alt_text (
    message_id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    alt_text TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    attachment_url TEXT NOT NULL
);

-- Chat summaries storage
CREATE TABLE IF NOT EXISTS chat_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT NOT NULL,
    start_timestamp DATETIME NOT NULL,
    end_timestamp DATETIME NOT NULL,
    summary TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- API interaction logs
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    requested_at INTEGER NOT NULL,
    received_at INTEGER NOT NULL,
    request TEXT NOT NULL,
    response TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    tags TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel_id);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_persona ON messages(persona_name);
CREATE INDEX IF NOT EXISTS idx_alt_text_channel ON image_alt_text(channel_id);
CREATE INDEX IF NOT EXISTS idx_summaries_channel ON chat_summaries(channel_id);
CREATE INDEX IF NOT EXISTS idx_summaries_timestamp ON chat_summaries(end_timestamp);
CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(requested_at);
CREATE INDEX IF NOT EXISTS idx_logs_status ON logs(status_code);
