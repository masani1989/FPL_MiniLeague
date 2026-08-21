import pytest
from unittest.mock import AsyncMock, patch
from continental_conquest import runner


@pytest.mark.asyncio
async def test_generate_schedule_persists_groups_members_and_matches():
    managers = [
        {"id": i, "player_name": f"P{i}", "team_name": "T", "fpl_entry_id": 1000 + i}
        for i in range(1, 27)
    ]
    with patch.object(runner.db, "get_cc_contest", new=AsyncMock(return_value={"id": 1, "schedule_frozen": False})), \
         patch.object(runner.db, "upsert_cc_group", new=AsyncMock()), \
         patch.object(runner.db, "upsert_cc_group_member", new=AsyncMock()), \
         patch.object(runner.db, "upsert_cc_fixture", new=AsyncMock()), \
         patch.object(runner.db, "get_managers", new=AsyncMock(return_value=managers)), \
         patch.object(runner.db, "get_manager_rank_history",
                      new=AsyncMock(return_value={i: [float(i)] for i in range(1, 27)})):
        # pass a bootstrap with a future GW1 deadline so generation proceeds
        result = await runner.generate_schedule("2026-27", 581588,
                                                bootstrap={"events": [{"id": 1, "deadline_time": "2099-01-01T00:00:00Z"}]})
        assert result["status"] == "ok"
        assert runner.db.upsert_cc_fixture.call_count == 312   # 312 league matches
        # two groups created
        assert runner.db.upsert_cc_group.call_count == 2
        assert runner.db.upsert_cc_group_member.call_count == 26


@pytest.mark.asyncio
async def test_generate_schedule_refuses_when_frozen():
    with patch.object(runner.db, "get_cc_contest", new=AsyncMock(return_value={"id": 1, "schedule_frozen": True})):
        result = await runner.generate_schedule("2026-27", 581588)
    assert result["status"] == "skipped" and "frozen" in result["reason"]


@pytest.mark.asyncio
async def test_generate_schedule_refuses_after_gw1_deadline():
    with patch.object(runner.db, "get_cc_contest", new=AsyncMock(return_value={"id": 1, "schedule_frozen": False})), \
         patch.object(runner.db, "freeze_schedule", new=AsyncMock()):
        result = await runner.generate_schedule("2026-27", 581588,
                                                bootstrap={"events": [{"id": 1, "deadline_time": "2000-01-01T00:00:00Z"}]})
    assert result["status"] == "skipped" and "deadline" in result["reason"]


@pytest.mark.asyncio
async def test_run_league_gw_scores_and_persists_matches():
    matches = [
        {"id": 1, "contest_id": 1, "group_id": 10, "gameweek": 1,
         "home_manager_id": 1, "away_manager_id": 2,
         "phase": "league", "round": "M1", "played": False},
    ]
    # managers 1,2 both have fpl_entry_id 1001,1002
    members = {1: {"manager_id": 1, "fpl_entry_id": 1001, "player_name": "A", "team_name": "T"},
               2: {"manager_id": 2, "fpl_entry_id": 1002, "player_name": "B", "team_name": "T"}}

    class FakeClient:
        async def get_bootstrap_static(self):
            return {"events": [{"id": 1, "finished": True}]}
        async def get_gw_live(self, gw):
            return {"elements": {}}
        async def get_entry_picks(self, entry, gw):
            # give home more points
            pts = 60 if entry == 1001 else 40
            return {"entry_history": {"points": pts, "event_transfers_cost": 0}, "picks": []}

    with patch.object(runner.db, "get_cc_contest", new=AsyncMock(return_value={"id": 1, "status": "league"})), \
         patch.object(runner.db, "get_cc_schedule_frozen", new=AsyncMock(return_value=False)), \
         patch.object(runner.db, "get_cc_matches_for_gw", new=AsyncMock(return_value=matches)), \
         patch.object(runner.db, "get_cc_group_members", new=AsyncMock(return_value=[
             {"manager_id": 1, "fpl_entry_id": 1001, "player_name": "A", "team_name": "T"},
             {"manager_id": 2, "fpl_entry_id": 1002, "player_name": "B", "team_name": "T"}])), \
         patch.object(runner.db, "upsert_cc_fixture", new=AsyncMock()):
        result = await runner.run_league_gw(1, client=FakeClient())
        assert result["status"] == "ok"
        call = runner.db.upsert_cc_fixture.call_args[0][0]
        assert call["home_score"] == 60 and call["away_score"] == 40
        assert call["result"] == "home"
        assert call["played"] is True


@pytest.mark.asyncio
async def test_run_league_gw_skips_unfinished():
    class FakeClient:
        async def get_bootstrap_static(self):
            return {"events": [{"id": 1, "finished": False}]}
    with patch.object(runner.db, "get_cc_contest", new=AsyncMock(return_value={"id": 1, "status": "league"})):
        result = await runner.run_league_gw(1, client=FakeClient())
    assert result["status"] == "skipped"


@pytest.mark.asyncio
async def test_finalize_groups_builds_knockouts():
    # two groups, each 13 members, results for each
    members_a = [{"manager_id": i, "player_name": f"A{i}", "team_name": "T"} for i in range(1, 14)]
    members_b = [{"manager_id": 100 + i, "player_name": f"B{i}", "team_name": "T"} for i in range(1, 14)]
    # fabricate standings rows (already ranked) -> simpler: stub compute by returning ordered standings
    with patch.object(runner.db, "get_cc_contest", new=AsyncMock(return_value={"id": 1, "status": "league", "phase": "league"})), \
         patch.object(runner.db, "get_cc_groups", new=AsyncMock(return_value=[{"id": 10, "name": "A"}, {"id": 11, "name": "B"}])), \
         patch.object(runner.db, "get_cc_group_members", new=AsyncMock(side_effect=[members_a, members_b])), \
         patch.object(runner.db, "get_cc_league_results", new=AsyncMock(return_value=[])), \
         patch.object(runner.db, "upsert_cc_standing", new=AsyncMock()), \
         patch.object(runner.db, "upsert_cc_tie", new=AsyncMock()), \
         patch.object(runner.db, "upsert_cc_fixture", new=AsyncMock()), \
         patch.object(runner.db, "complete_league_phase", new=AsyncMock()):
        result = await runner.finalize_groups("2026-27", 581588)
        assert result["status"] == "ok"
        # 8 UCL + 4 UEL ties
        assert runner.db.upsert_cc_tie.call_count == 12
        # leg matches: UCL 8 ties * 2 legs + UEL 4 ties * 2 legs = 24
        assert runner.db.upsert_cc_fixture.call_count == 24