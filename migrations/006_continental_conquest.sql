create table if not exists cc_contest (
    id serial primary key,
    season_id text not null references seasons(id),
    league_id int not null references league(id),
    name text not null default 'Continental Conquest',
    status text not null default 'setup',   -- setup|league|knockouts|completed
    phase text not null default 'league',   -- league|ucl|uel|final|done
    current_gw int,
    winner_manager_id int references managers(id),
    runner_up_manager_id int references managers(id),
    schedule_frozen boolean default false,
    created_at timestamp with time zone default now(),
    updated_at timestamp with time zone default now(),
    unique (season_id, league_id)
);

create table if not exists cc_groups (
    id serial primary key,
    contest_id int not null references cc_contest(id),
    name text not null,                      -- 'A' | 'B'
    unique (contest_id, name)
);

create table if not exists cc_group_members (
    id serial primary key,
    contest_id int not null references cc_contest(id),
    group_id int not null references cc_groups(id),
    manager_id int not null references managers(id),
    seed_rank numeric,                       -- 3-season avg rank (null if no history)
    player_name text not null,
    team_name text,
    unique (contest_id, manager_id)
);

create table if not exists cc_matches (
    id serial primary key,
    contest_id int not null references cc_contest(id),
    phase text not null,                      -- league | ucl | uel
    competition text,                         -- ucl | uel (null for league)
    round text,                               -- league matchday N | ro16 | qf | sf | final
    gameweek int not null,                    -- FPL gw
    leg int,                                  -- 1|2 (null for league)
    group_id int references cc_groups(id),    -- set for league matches
    tie_id int,                               -- set for knockout legs
    home_manager_id int not null references managers(id),
    away_manager_id int not null references managers(id),
    home_score int,                           -- league: net gw score | knockout: first xi
    away_score int,
    home_gross int,                           -- league: net gw score (gw_score - transfer_cost); null for knockouts
    away_gross int,
    home_first_xi int,                         -- first xi (knockout phase); null for league
    away_first_xi int,
    result text,                              -- home | away | draw
    active_chip_home text,
    active_chip_away text,
    played boolean default false,
    created_at timestamp with time zone default now(),
    updated_at timestamp with time zone default now(),
    unique (contest_id, phase, gameweek, home_manager_id, away_manager_id)
);
create index if not exists idx_cc_matches_gw on cc_matches (contest_id, gameweek);

create table if not exists cc_ties (
    id serial primary key,
    contest_id int not null references cc_contest(id),
    competition text not null,                -- ucl | uel
    round text not null,                       -- ro16 | qf | sf | final
    tie_index int not null,                    -- order within the round
    home_manager_id int not null references managers(id),
    away_manager_id int not null references managers(id),
    leg1_match_id int references cc_matches(id),
    leg2_match_id int references cc_matches(id),
    winner_manager_id int references managers(id),
    loser_manager_id int references managers(id),
    tiebreak_note text,
    coin_toss_required boolean default false,
    coin_toss_winner text,
    resolved boolean default false,
    next_tie_id int references cc_ties(id),
    created_at timestamp with time zone default now(),
    unique (contest_id, competition, round, tie_index)
);

alter table cc_matches
    add constraint cc_matches_tie_id_fkey
    foreign key (tie_id) references cc_ties(id);
    
create table if not exists cc_standings (
    id serial primary key,
    contest_id int not null references cc_contest(id),
    group_id int not null references cc_groups(id),
    manager_id int not null references managers(id),
    player_name text not null,
    team_name text,
    played int default 0,
    wins int default 0,
    draws int default 0,
    losses int default 0,
    points int default 0,
    score_for int default 0,                   -- aggregate gross
    score_against int default 0,
    goals_scored int default 0,
    goals_conceded int default 0,
    clean_sheets int default 0,
    assists int default 0,
    bench_points int default 0,
    group_rank int,
    qualification text,                        -- ucl | uel | eliminated
    unique (contest_id, manager_id)
);

insert into cc_contest (season_id, league_id, name, status, phase)
select '2026-27', 581588, 'Continental Conquest 2026/27', 'setup', 'league'
where not exists (select 1 from cc_contest where season_id='2026-27' and league_id=581588);