CREATE TABLE threads (
    id          text PRIMARY KEY,
    owner_key   text NOT NULL,
    title       text,
    settings    jsonb NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX threads_owner_key_idx ON threads (owner_key);

CREATE TABLE messages (
    id              text PRIMARY KEY,
    thread_id       text NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    role            text NOT NULL CHECK (role IN ('user', 'assistant', 'settings')),
    content         text NOT NULL,
    citations       jsonb,
    settings_delta  jsonb,
    status          text NOT NULL DEFAULT 'complete' CHECK (status IN ('complete', 'interrupted')),
    tokens          int,
    cost            numeric,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX messages_thread_created_idx ON messages (thread_id, created_at);
