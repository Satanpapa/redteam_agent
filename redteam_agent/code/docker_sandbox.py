"""Docker sandbox manager for isolated Kali execution."""

from __future__ import annotations

import io
import logging
import tarfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import docker
from docker.errors import DockerException, NotFound

logger = logging.getLogger(__name__)


@dataclass
class SandboxConfig:
    image: str
    cpu_quota: int = 100000
    mem_limit: str = "2g"
    pids_limit: int = 512
    network_mode: str = "none"
    read_only_rootfs: bool = False
    volumes: list[str] | None = None
    snapshots_path: str = "./state/snapshots"


class DockerSandboxManager:
    def __init__(self, config: SandboxConfig) -> None:
        self.config = config
        self.client = docker.from_env()
        self.snapshots_path = Path(config.snapshots_path)
        self.snapshots_path.mkdir(parents=True, exist_ok=True)

    def create(self, name: str, command: str = "sleep infinity") -> str:
        logger.info("Creating sandbox %s", name)
        host_config_volumes = self._parse_volumes(self.config.volumes or [])
        container = self.client.containers.run(
            self.config.image,
            name=name,
            command=command,
            detach=True,
            tty=True,
            stdin_open=True,
            cpu_quota=self.config.cpu_quota,
            mem_limit=self.config.mem_limit,
            pids_limit=self.config.pids_limit,
            network_mode=self.config.network_mode,
            read_only=self.config.read_only_rootfs,
            volumes=host_config_volumes,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],
        )
        return container.id

    def start(self, container_id: str) -> None:
        self._get_container(container_id).start()

    def stop(self, container_id: str, timeout: int = 10) -> None:
        container = self._get_container(container_id)
        container.stop(timeout=timeout)

    def remove(self, container_id: str, force: bool = False) -> None:
        container = self._get_container(container_id)
        container.remove(force=force)

    def exec(self, container_id: str, cmd: str, timeout: int = 180) -> dict[str, Any]:
        container = self._get_container(container_id)
        started = time.time()
        result = container.exec_run(cmd, demux=True, tty=False)
        stdout, stderr = result.output if isinstance(result.output, tuple) else (result.output, b"")
        return {
            "exit_code": result.exit_code,
            "stdout": (stdout or b"").decode("utf-8", errors="replace"),
            "stderr": (stderr or b"").decode("utf-8", errors="replace"),
            "duration_seconds": time.time() - started,
            "timeout": timeout,
        }

    def snapshot(self, container_id: str, tag: str) -> str:
        container = self._get_container(container_id)
        image = container.commit(repository="redteam-agent-snapshots", tag=tag)
        logger.info("Created snapshot image=%s", image.id)
        return image.id

    def restore(self, name: str, snapshot_tag: str) -> str:
        image_ref = f"redteam-agent-snapshots:{snapshot_tag}"
        self._remove_if_exists(name)
        container = self.client.containers.run(
            image_ref,
            name=name,
            command="sleep infinity",
            detach=True,
            tty=True,
            stdin_open=True,
            network_mode=self.config.network_mode,
            cpu_quota=self.config.cpu_quota,
            mem_limit=self.config.mem_limit,
            pids_limit=self.config.pids_limit,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],
        )
        return container.id

    def export_filesystem(self, container_id: str, output_tar: str) -> Path:
        container = self._get_container(container_id)
        output_path = Path(output_tar)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        stream, _ = container.get_archive("/")
        with output_path.open("wb") as f:
            for chunk in stream:
                f.write(chunk)
        return output_path

    def copy_to_container(self, container_id: str, src_path: str, dst_path: str) -> None:
        container = self._get_container(container_id)
        src = Path(src_path)
        if not src.exists():
            raise FileNotFoundError(src_path)
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode="w") as tar:
            tar.add(src, arcname=src.name)
        data.seek(0)
        ok = container.put_archive(dst_path, data.read())
        if not ok:
            raise DockerException(f"Failed to copy {src_path} to container")

    def inspect(self, container_id: str) -> dict[str, Any]:
        container = self._get_container(container_id)
        container.reload()
        attrs = container.attrs
        return {
            "id": attrs["Id"],
            "name": attrs["Name"],
            "state": attrs["State"],
            "network_mode": attrs["HostConfig"].get("NetworkMode"),
            "memory": attrs["HostConfig"].get("Memory"),
            "cpu_quota": attrs["HostConfig"].get("CpuQuota"),
            "mounts": attrs.get("Mounts", []),
        }

    def _get_container(self, container_id: str):
        try:
            return self.client.containers.get(container_id)
        except NotFound as exc:
            raise ValueError(f"Container not found: {container_id}") from exc

    def _remove_if_exists(self, name: str) -> None:
        try:
            container = self.client.containers.get(name)
            container.remove(force=True)
        except NotFound:
            return

    @staticmethod
    def _parse_volumes(volume_specs: list[str]) -> dict[str, dict[str, str]]:
        result: dict[str, dict[str, str]] = {}
        for spec in volume_specs:
            host, cont, mode = spec.split(":")
            result[str(Path(host).resolve())] = {"bind": cont, "mode": mode}
        return result
