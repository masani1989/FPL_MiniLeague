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
