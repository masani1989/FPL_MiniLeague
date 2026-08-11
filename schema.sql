-- FPL Fantasy Kings - Phase 1 Supabase schema
-- Run this in the Supabase SQL Editor before running the app or migration.

-- Seasons lookup. One active season is sufficient for Phase 1.
create table if not exists seasons (
    id text primary key,
    name text not null,
    is_active boolean default false
);

insert into seasons (id, name, is_active)
values ('2026-27', 'Fantasy Kings 2026/27', true)
on conflict (id) do nothing;

-- Mini-league reference table.
create table if not exists league (
    id int primary key,
    fpl_league_id int not null,
    name text not null,
    season_id text not null references seasons(id),
    created_at timestamp with time zone default now(),
    updated_at timestamp with time zone default now(),
    unique (fpl_league_id, season_id)
);

-- Manager reference table. One row per FPL entry per league.
create table if not exists managers (
    id serial primary key,
    fpl_entry_id int not null,
    league_id int not null references league(id),
    player_name text not null,
    team_name text not null,
    created_at timestamp with time zone default now(),
    updated_at timestamp with time zone default now(),
    unique (fpl_entry_id, league_id)
);

-- Gameweek reference table. One row per FPL gameweek per season.
create table if not exists gameweek (
    id serial primary key,
    fpl_gameweek_id int not null,
    season_id text not null references seasons(id),
    name text not null,
    deadline_time timestamp with time zone,
    finished boolean default false,
    is_current boolean default false,
    created_at timestamp with time zone default now(),
    updated_at timestamp with time zone default now(),
    unique (fpl_gameweek_id, season_id)
);

-- Overall mini-league standings (replaces the 'Overall' worksheet).
create table if not exists overall_standings (
    id serial primary key,
    manager_id int not null references managers(id),
    player_name text not null,
    rank int not null,
    points int not null,
    last_rank int,
    season_id text not null references seasons(id),
    updated_at timestamp with time zone default now(),
    unique (manager_id, season_id)
);

-- Per-gameweek results (replaces the 'Gameweek' worksheet).
create table if not exists gameweek_results (
    id serial primary key,
    manager_id int not null references managers(id),
    gameweek_id int not null references gameweek(id),
    player_name text not null,
    gross int not null,
    transfer int not null,
    points int not null,
    rank int,
    season_id text not null references seasons(id),
    updated_at timestamp with time zone default now(),
    unique (manager_id, gameweek_id, season_id)
);

-- Monthly aggregated results (replaces the 'Monthly' worksheet).
create table if not exists monthly_results (
    id serial primary key,
    manager_id int not null references managers(id),
    player_name text not null,
    points int not null,
    rank int,
    month text not null,
    season_id text not null references seasons(id),
    updated_at timestamp with time zone default now(),
    unique (manager_id, month, season_id)
);

-- Refresh audit log (replaces the 'DataDate' worksheet).
create table if not exists data_refresh_log (
    id serial primary key,
    refreshed_at timestamp with time zone default now(),
    gameweek_id int references gameweek(id),
    status text,
    notes text
);

-- Index for the latest refresh lookup used by the home page.
create index if not exists idx_data_refresh_log_refreshed_at
    on data_refresh_log (refreshed_at desc);

-- Gameweek winnings: one row per manager per finished gameweek.
create table if not exists gw_winnings (
    id serial primary key,
    manager_id int not null references managers(id),
    gameweek_id int not null references gameweek(id),
    player_name text not null,
    rank int not null,
    count int not null,
    pot int not null default 300,
    winnings numeric(10, 2) not null,
    season_id text not null references seasons(id),
    updated_at timestamp with time zone default now(),
    unique (manager_id, gameweek_id, season_id)
);

-- Monthly winnings: one row per manager per completed month.
create table if not exists monthly_winnings (
    id serial primary key,
    manager_id int not null references managers(id),
    month text not null,
    player_name text not null,
    rank int not null,
    count int not null,
    pot int not null default 530,
    winnings numeric(10, 2) not null,
    season_id text not null references seasons(id),
    updated_at timestamp with time zone default now(),
    unique (manager_id, month, season_id)
);

-- Overall season prizes: top 4 after the season ends (GW 38 finished).
create table if not exists overall_prizes (
    id serial primary key,
    manager_id int not null references managers(id),
    final_rank int not null,
    prize_amount int not null,
    season_id text not null references seasons(id),
    updated_at timestamp with time zone default now(),
    unique (manager_id, season_id)
);

-- Pre-aggregated summary used by the Total Winnings tab and metric widgets.
create table if not exists winnings_summary (
    id serial primary key,
    manager_id int not null references managers(id),
    player_name text not null,
    gw_winnings numeric(10, 2) not null default 0,
    monthly_winnings numeric(10, 2) not null default 0,
    overall_prize int not null default 0,
    total_winnings numeric(10, 2) not null default 0,
    season_id text not null references seasons(id),
    updated_at timestamp with time zone default now(),
    unique (manager_id, season_id)
);
