"""Docker sandbox manager with lifecycle, isolation and snapshots."""

from __future__ import annotations

import logging
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any

import docker
from docker.models.containers import Container

logger = logging.getLogger(__name__)


class DockerSandboxManager:
    def __init__(
        self,
        image: str,
        network_name: str,
        mount_base: str,
        snapshot_dir: str,
        cpu_quota: int = 50000,
        mem_limit: str = "2g",
        pids_limit: int = 256,
        read_only_root: bool = False,
    ) -> None:
        self.client = docker.from_env()
        self.image = image
        self.network_name = network_name
        self.mount_base = Path(mount_base)
        self.snapshot_dir = Path(snapshot_dir)
        self.cpu_quota = cpu_quota
        self.mem_limit = mem_limit
        self.pids_limit = pids_limit
        self.read_only_root = read_only_root
        self.mount_base.mkdir(parents=True, exist_ok=True)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_network()

    def _ensure_network(self) -> None:
        if not any(net.name == self.network_name for net in self.client.networks.list()):
            self.client.networks.create(self.network_name, driver="bridge", internal=True)

    def start(self, name: str, command: str = "sleep infinity") -> Container:
        host_dir = self.mount_base / name
        host_dir.mkdir(parents=True, exist_ok=True)
        container = self.client.containers.run(
            self.image,
            command=command,
            name=name,
            detach=True,
            tty=True,
            stdin_open=True,
            network=self.network_name,
            cpu_quota=self.cpu_quota,
            mem_limit=self.mem_limit,
            pids_limit=self.pids_limit,
            read_only=self.read_only_root,
            security_opt=["no-new-privileges:true"],
            cap_drop=["ALL"],
            volumes={str(host_dir): {"bind": "/workspace", "mode": "rw"}},
        )
        logger.info("Sandbox %s started", name)
        return container

    def exec(self, container: Container, cmd: str, timeout: int = 180) -> dict[str, Any]:
        started = time.time()
        result = container.exec_run(cmd, demux=True)
        stdout, stderr = result.output if result.output else (b"", b"")
        elapsed = time.time() - started
        if elapsed > timeout:
            logger.warning("Command exceeded timeout hint: %.2fs > %ss", elapsed, timeout)
        return {
            "exit_code": result.exit_code,
            "stdout": (stdout or b"").decode(errors="ignore"),
            "stderr": (stderr or b"").decode(errors="ignore"),
            "elapsed": elapsed,
        }

    def snapshot(self, container: Container, tag: str) -> str:
        image_tag = f"{container.name}:{tag}"
        container.commit(repository=container.name, tag=tag)
        archive_path = self.snapshot_dir / f"{container.name}_{tag}.tar"
        img = self.client.images.get(image_tag)
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            for chunk in img.save(named=True):
                tmp.write(chunk)
            tmp.flush()
            with tarfile.open(archive_path, "w") as out_tar:
                out_tar.add(tmp.name, arcname=f"{image_tag}.tar")
        logger.info("Snapshot created: %s", archive_path)
        return str(archive_path)

    def restore(self, snapshot_path: str, name: str) -> Container:
        snapshot_file = Path(snapshot_path)
        with tarfile.open(snapshot_file, "r") as t:
            member = t.getmembers()[0]
            extracted = t.extractfile(member)
            if extracted is None:
                raise RuntimeError("Invalid snapshot archive")
            self.client.images.load(extracted.read())
        image_ref = member.name.replace(".tar", "")
        return self.start(name=name, command="sleep infinity") if image_ref else self.start(name=name)

    def stop(self, container: Container, remove: bool = True) -> None:
        try:
            container.stop(timeout=3)
        finally:
            if remove:
                container.remove(force=True)
        logger.info("Sandbox %s stopped", container.name)

    def destroy_network(self) -> None:
        nets = [n for n in self.client.networks.list() if n.name == self.network_name]
        for net in nets:
            net.remove()
        logger.info("Network %s removed", self.network_name)
