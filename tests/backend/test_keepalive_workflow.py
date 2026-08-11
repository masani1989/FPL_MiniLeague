import yaml
from pathlib import Path


def test_keepalive_workflow_pings_health_on_schedule():
    path = Path(".github/workflows/keepalive.yml")
    assert path.exists(), "keepalive.yml must exist"
    with path.open() as f:
        data = yaml.safe_load(f)

    triggers = data.get("on") or data.get(True)  # PyYAML coerces `on:` to True
    assert "schedule" in triggers, "keepalive must have a schedule trigger"
    crons = [s["cron"] for s in triggers["schedule"]]
    assert crons, "keepalive must have at least one cron entry"
    assert "workflow_dispatch" in triggers, "keepalive must allow manual dispatch"

    job = data["jobs"]["keepalive"]
    run_text = " ".join(s.get("run", "") for s in job["steps"])
    assert "curl" in run_text and "/health" in run_text, "keepalive must curl the /health endpoint"