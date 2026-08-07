import os
import runpy
from unittest.mock import patch, MagicMock


def test_run_backend_uses_port_env_var():
    with patch.dict(os.environ, {"PORT": "12345"}, clear=False):
        with patch("uvicorn.run") as mock_run:
            with patch("backend.main.app", MagicMock()):
                runpy.run_path("scripts/run_backend.py", run_name="__main__")
    mock_run.assert_called_once()
    _, kwargs = mock_run.call_args
    assert kwargs["port"] == 12345
    assert kwargs["host"] == "0.0.0.0"
