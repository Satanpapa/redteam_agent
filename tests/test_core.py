import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "code"
spec = importlib.util.spec_from_file_location("rt_code", PKG / "__init__.py", submodule_search_locations=[str(PKG)])
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules["rt_code"] = module
spec.loader.exec_module(module)

from rt_code.decision_engine import DecisionConfig, DecisionEngine
from rt_code.models import ActionCandidate, ToolCategory, WorldNode, NodeType
from rt_code.tool_layer import InputNormalizer, DataEnricher, ToolLayer
from rt_code.world_model import WorldModel


def test_normalize_ip_target():
    assert InputNormalizer.normalize_target(" 192.168.1.10 ") == "192.168.1.10"


def test_normalize_hostname_target():
    assert InputNormalizer.normalize_target("HTTP://Example.COM/path") == "example.com"


def test_cve_enrichment_matches_service():
    enricher = DataEnricher(cve_db_path="/tmp/absent_cve_db.json")
    data = enricher.enrich_service("smb", "1.0")
    assert len(data["candidate_cves"]) >= 1


def test_decision_engine_selects_candidate():
    engine = DecisionEngine(DecisionConfig())
    cands = [
        ActionCandidate(
            id="a1",
            title="scan",
            category=ToolCategory.RECON,
            command="echo hi",
            rationale="x",
            expected_outcome="y",
            base_scores={"stealth": 0.5, "impact": 0.6, "speed": 0.7, "confidence": 0.8},
        ),
        ActionCandidate(
            id="a2",
            title="scan2",
            category=ToolCategory.RECON,
            command="echo hi",
            rationale="x",
            expected_outcome="y",
            base_scores={"stealth": 0.6, "impact": 0.5, "speed": 0.6, "confidence": 0.7},
        ),
    ]
    result = engine.decide(cands)
    assert result.action_id in {"a1", "a2"}


def test_world_model_node_roundtrip(tmp_path):
    db = tmp_path / "wm.db"
    wm = WorldModel(str(db))
    wm.upsert_node(WorldNode(node_id="host1", node_type=NodeType.HOST, properties={"ip": "10.0.0.1"}))
    wm.save()
    wm2 = WorldModel(str(db))
    assert "host1" in wm2.graph.nodes


def test_toollayer_parsing_nmap_summary():
    layer = ToolLayer(timeout=1)
    out = "22/tcp open ssh OpenSSH 8.9\n80/tcp open http Apache 2.4.52"
    parsed = layer.parse_nmap_summary(out)
    assert len(parsed["open_ports"]) == 2
