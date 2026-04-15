import pytest

pytest.importorskip("msgpack")

from rtcode.tool_layer import NmapOutputNormalizer


def test_nmap_normalizer_extracts_service():
    data = "Host: 10.0.0.5 ()\tPorts: 22/open/tcp//ssh///OpenSSH 8.2p1/, 80/closed/tcp//http///"
    parsed = NmapOutputNormalizer().normalize(data)
    assert len(parsed) == 1
    assert parsed[0].port == 22
    assert parsed[0].service == "ssh"
