-- FPL Fantasy Kings - Last Man Standing pilot contest (no prize).
create table if not exists lms_contest (
    id serial primary key,
    season_id text not null references seasons(id),
    league_id int not null references league(id),
    name text not null default 'Last Man Standing',
    status text not null default 'active',       -- 'active' | 'completed'
    started_gw int not null,                      -- first GW scored (1)
    current_gw int,                               -- last GW processed
    winner_manager_id int references managers(id),
    created_at timestamp with time zone default now(),
    updated_at timestamp with time zone default now(),
    unique (season_id, league_id)
);

create table if not exists lms_standings (
    id serial primary key,
    contest_id int not null references lms_contest(id),
    manager_id int not null references managers(id),
    player_name text not null,
    team_name text,
    is_alive boolean default true,
    eliminated_gw int,
    eliminated_at timestamp with time zone,
    final_rank int,                               -- 1 = winner
    created_at timestamp with time zone default now(),
    updated_at timestamp with time zone default now(),
    unique (contest_id, manager_id)
);
create index if not exists idx_lms_standings_contest
    on lms_standings (contest_id, is_alive);

create table if not exists lms_gameweek_scores (
    id serial primary key,
    contest_id int not null references lms_contest(id),
    manager_id int not null references managers(id),
    gameweek_id int not null references gameweek(id),
    fpl_gameweek_id int not null,
    player_name text not null,
    first_xi_points int not null,
    captain_element int,
    captain_multiplier int,
    vice_captain_element int,
    goals_scored int not null default 0,
    goals_conceded int not null default 0,
    clean_sheets int not null default 0,
    assists int not null default 0,
    bench_points int not null default 0,
    is_eliminated boolean default false,
    elimination_tiebreak text,
    coin_toss_winner text,                         -- 'win' | 'lose' | null
    coin_toss_reason text,
    created_at timestamp with time zone default now(),
    updated_at timestamp with time zone default now(),
    unique (contest_id, manager_id, fpl_gameweek_id)
);
create index if not exists idx_lms_gw_scores_gw
    on lms_gameweek_scores (contest_id, fpl_gameweek_id);

create table if not exists lms_eliminations (
    id serial primary key,
    contest_id int not null references lms_contest(id),
    gameweek_id int not null references gameweek(id),
    fpl_gameweek_id int not null,
    eliminated_manager_id int not null references managers(id),
    eliminated_player_name text not null,
    tiebreak_note text,
    coin_toss_required boolean default false,
    coin_toss_outcome text,
    alive_before int,
    alive_after int,
    created_at timestamp with time zone default now(),
    unique (contest_id, fpl_gameweek_id)
);

insert into lms_contest (season_id, league_id, name, status, started_gw)
select '2026-27', 581588, 'Last Man Standing 2026/27', 'active', 1
where not exists (
    select 1 from lms_contest where season_id = '2026-27' and league_id = 581588
);