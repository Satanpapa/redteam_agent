"""Docker sandbox manager for isolated offensive command execution."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import docker
from docker.models.containers import Container

logger = logging.getLogger(__name__)


@dataclass
class SandboxConfig:
    image: str
    network_name: str
    cpu_quota: int = 100000
    mem_limit: str = "2g"
    pids_limit: int = 256
    volumes: list[str] | None = None
    default_timeout: int = 600


class DockerSandboxManager:
    def __init__(self, config: SandboxConfig):
        self.config = config
        self.client = docker.from_env()
        self.low_level = docker.APIClient(base_url="unix://var/run/docker.sock")
        self._ensure_network()

    def _ensure_network(self) -> None:
        existing = [n.name for n in self.client.networks.list()]
        if self.config.network_name not in existing:
            self.client.networks.create(self.config.network_name, driver="bridge", internal=True)
            logger.info("Created isolated network: %s", self.config.network_name)

    def create_container(self, name: str, command: str = "sleep infinity") -> Container:
        volumes = {}
        for v in self.config.volumes or []:
            src, dst, mode = v.split(":")
            Path(src).mkdir(parents=True, exist_ok=True)
            volumes[str(Path(src).resolve())] = {"bind": dst, "mode": mode}

        container = self.client.containers.run(
            image=self.config.image,
            name=name,
            command=command,
            detach=True,
            tty=True,
            stdin_open=True,
            network=self.config.network_name,
            mem_limit=self.config.mem_limit,
            cpu_quota=self.config.cpu_quota,
            pids_limit=self.config.pids_limit,
            volumes=volumes,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
        )
        logger.info("Created sandbox container: %s", container.id)
        return container

    def exec(self, container: Container, command: str, timeout: int | None = None) -> dict[str, Any]:
        timeout = timeout or self.config.default_timeout
        start = time.time()
        result = container.exec_run(command, demux=True)
        elapsed = time.time() - start
        stdout, stderr = result.output if result.output else (b"", b"")
        if elapsed > timeout:
            raise TimeoutError(f"Command timeout in sandbox after {timeout}s: {command}")
        return {
            "exit_code": result.exit_code,
            "stdout": (stdout or b"").decode(errors="replace"),
            "stderr": (stderr or b"").decode(errors="replace"),
            "elapsed": elapsed,
        }

    def snapshot(self, container: Container, tag: str) -> str:
        image = container.commit(repository="redteam-snapshot", tag=tag)
        snapshot_ref = f"{image.tags[0] if image.tags else image.id}"
        logger.info("Created snapshot %s", snapshot_ref)
        return snapshot_ref

    def restore(self, snapshot_ref: str, name: str) -> Container:
        logger.info("Restoring container %s from %s", name, snapshot_ref)
        return self.client.containers.run(
            snapshot_ref,
            name=name,
            detach=True,
            tty=True,
            stdin_open=True,
            network=self.config.network_name,
            mem_limit=self.config.mem_limit,
            cpu_quota=self.config.cpu_quota,
            pids_limit=self.config.pids_limit,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
        )

    def stop_remove(self, container: Container) -> None:
        try:
            container.stop(timeout=5)
        finally:
            container.remove(force=True)
            logger.info("Removed sandbox container: %s", container.id)

    def cleanup(self, prefix: str = "rt-") -> None:
        for c in self.client.containers.list(all=True):
            if c.name.startswith(prefix):
                try:
                    c.remove(force=True)
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning("Cleanup failed for %s: %s", c.name, exc)
