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

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel_id);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_persona ON messages(persona_name);