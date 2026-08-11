-- Telegram chat registrations (groups and private chats).
create table if not exists telegram_chats (
    id serial primary key,
    chat_id bigint not null unique,
    chat_type text not null,              -- 'group' or 'private'
    title text,
    manager_id int references managers(id),
    fpl_entry_id int,
    is_active boolean default true,
    created_at timestamp with time zone default now(),
    updated_at timestamp with time zone default now()
);

-- Announcements already posted so we don't double-post after restarts.
create table if not exists telegram_announcements_log (
    id serial primary key,
    chat_id bigint not null,
    kind text not null,                   -- 'deadline', 'gw_results', 'monthly_results', 'pre_gw_suggestions'
    trigger_key text not null,            -- e.g. 'gw_7' or 'month_August'
    text text not null,
    posted_at timestamp with time zone default now(),
    unique (chat_id, kind, trigger_key)
);

-- Index for quick duplicate checks.
create index if not exists idx_announcements_log_trigger
    on telegram_announcements_log (chat_id, kind, trigger_key);
