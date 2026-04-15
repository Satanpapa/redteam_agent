import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1] / "code"))

from tool_layer import ToolLayer


def test_nikto_normalizer():
    tl = ToolLayer()
    out = tl.normalize_tool_output("nikto", "+ /admin: Found admin panel")
    assert out["findings"][0]["path"] == "/admin"


def test_target_normalization_network():
    assert ToolLayer.normalize_target("192.168.1.5/24") == "192.168.1.0/24"
