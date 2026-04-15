import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1] / "code"))

import pytest

from models import AgentState


def test_agent_state_requires_non_empty_objective():
    with pytest.raises(ValueError):
        AgentState(run_id="1", objective="   ")
