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
    env_groups = [e.get("name") for e in service.get("envVarGroups", [])]
    assert "fpl-backend-secrets" in env_groups
