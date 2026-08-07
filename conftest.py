import os
import sys

# Ensure the repository root is on PYTHONPATH so `backend.*` imports work
# when running pytest, scripts, or uvicorn from any directory.
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
