import sys
from pathlib import Path

import pandas as pd
import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


@pytest.fixture
def sample_overall():
    return pd.DataFrame({
        "Rank": [1, 2],
        "Player": ["A B", "C D"],
        "Points": [100, 90],
        "Last_Rank": [2, 1],
    })


@pytest.fixture
def sample_gameweek():
    return pd.DataFrame({
        "Player": ["A B", "C D", "A B"],
        "Gross": [50, 45, 55],
        "Transfer": [4, 0, 2],
        "Points": [46, 45, 53],
        "Rank": [1, 2, 1],
        "Gameweek": [1, 1, 2],
    })


@pytest.fixture
def sample_monthly():
    return pd.DataFrame({
        "Player": ["A B", "C D"],
        "Points": [99, 45],
        "Rank": [1, 2],
        "Month": ["August", "August"],
    })


@pytest.fixture(autouse=True)
def _isolate_streamlit_caches():
    """Clear Streamlit caches before each test to avoid cross-test pollution."""
    import streamlit as st

    try:
        st.cache_data.clear()
    except Exception:
        pass
    try:
        st.cache_resource.clear()
    except Exception:
        pass
    yield
