import yaml
from pathlib import Path


def test_render_yaml_exists_and_is_valid():
    path = Path("render.yaml")
    assert path.exists(), "render.yaml must exist"
    with path.open() as f:
        data = yaml.safe_load(f)
    assert "services" in data
    service = data["services"][0]
    assert service["type"] == "web"
    assert "buildCommand" in service
    assert "startCommand" in service
    assert "requirements-backend.txt" in service["buildCommand"]
    env_groups = [e.get("name") for e in service.get("envVarGroups", [])]
    assert "fpl-backend-secrets" in env_groups


def test_render_yaml_has_keepalive_cron_service():
    path = Path("render.yaml")
    with path.open() as f:
        data = yaml.safe_load(f)
    cron_services = [s for s in data["services"] if s.get("type") == "cron"]
    assert len(cron_services) == 1, "expected one keep-alive cron service"
    cron = cron_services[0]
    assert cron["name"] == "fpl-keepalive"
    assert "schedule" in cron
    assert "0 0 1 1 0" not in cron["schedule"]  # sanity: not a once-a-year cron
    assert "health" in cron["command"]
