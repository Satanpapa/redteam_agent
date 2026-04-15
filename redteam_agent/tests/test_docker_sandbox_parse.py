import pytest

pytest.importorskip("docker")

from rtcode.docker_sandbox import DockerSandboxManager


def test_parse_volumes():
    parsed = DockerSandboxManager._parse_volumes(["./tmp:/workspace:rw"])
    assert list(parsed.values())[0]["bind"] == "/workspace"
    assert list(parsed.values())[0]["mode"] == "rw"
