-- Messages table to store all interactions
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_message_id TEXT UNIQUE,  -- Added to track Discord message IDs
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
    requested_at BIGINT NOT NULL,
    received_at BIGINT NOT NULL,
    request TEXT NOT NULL,
    response TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    tags TEXT,
    user_id TEXT,
    guild_id TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- User settings storage
CREATE TABLE IF NOT EXISTS user_settings (
    user_id TEXT PRIMARY KEY,
    store_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel_id);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_persona ON messages(persona_name);
CREATE INDEX IF NOT EXISTS idx_messages_discord_id ON messages(discord_message_id);  -- Added index for Discord message ID
CREATE INDEX IF NOT EXISTS idx_summaries_channel ON chat_summaries(channel_id);
CREATE INDEX IF NOT EXISTS idx_summaries_timestamp ON chat_summaries(end_timestamp);
CREATE INDEX IF NOT EXISTS idx_logs_requested_at ON logs(requested_at);
CREATE INDEX IF NOT EXISTS idx_logs_status_code ON logs(status_code);
CREATE INDEX IF NOT EXISTS idx_logs_user_id ON logs(user_id);
CREATE INDEX IF NOT EXISTS idx_logs_guild_id ON logs(guild_id);
