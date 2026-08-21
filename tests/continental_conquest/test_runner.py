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