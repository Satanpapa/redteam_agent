"""
Docker Sandbox Manager for Red Team Agent v2.0

Provides isolated Kali Linux environment with:
- Full lifecycle management
- Snapshot/restore before dangerous operations
- Resource limits (CPU, memory, network)
- Network isolation
- Volume control
- Health monitoring
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

import docker
from docker.models.containers import Container
from docker.types import LogConfig

from .models import ContainerConfig, SnapshotInfo

logger = logging.getLogger(__name__)


class DockerSandboxManager:
    """
    Manages isolated Docker containers for red team operations.
    
    Features:
    - Container lifecycle management
    - Snapshot/restore functionality
    - Resource limits enforcement
    - Network isolation
    - Volume management
    - Health monitoring
    """
    
    def __init__(
        self,
        image: str = "kalilinux/kali-rolling:latest",
        container_prefix: str = "redteam-sandbox",
        network_mode: str = "isolated",
        bridge_name: str = "redteam-net",
        resource_limits: Optional[Dict[str, Any]] = None,
        volumes: Optional[List[Dict[str, Any]]] = None,
    ):
        """Initialize Docker sandbox manager."""
        self.image = image
        self.container_prefix = container_prefix
        self.network_mode = network_mode
        self.bridge_name = bridge_name
        
        self.cpu_count = (resource_limits or {}).get("cpu_count", 2.0)
        self.memory_limit = (resource_limits or {}).get("memory_limit", "4g")
        self.pids_limit = (resource_limits or {}).get("pids_limit", 100)
        
        self.volumes_config = volumes or []
        
        try:
            self.client = docker.from_env()
            self._verify_docker_access()
        except docker.errors.DockerException as e:
            logger.warning(f"Docker initialization warning: {e}")
            self.client = None
        
        self.containers: Dict[str, Container] = {}
        self.snapshots: Dict[str, SnapshotInfo] = {}
        
        self._setup_network()
        logger.info(f"DockerSandboxManager initialized with image: {image}")
    
    def _verify_docker_access(self) -> None:
        """Verify Docker daemon access."""
        try:
            self.client.ping()
            logger.debug("Docker daemon connection verified")
        except Exception as e:
            raise RuntimeError(f"Cannot connect to Docker daemon: {e}")
    
    def _setup_network(self) -> None:
        """Create isolated network if needed."""
        if self.network_mode == "isolated" and self.client:
            try:
                existing = self.client.networks.list(names=[self.bridge_name])
                if not existing:
                    ipam_pool = docker.types.IPAMPool(
                        subnet="172.28.0.0/16",
                        gateway="172.28.0.1",
                    )
                    ipam_config = docker.types.IPAMConfig(pool_configs=[ipam_pool])
                    self.client.networks.create(
                        self.bridge_name,
                        driver="bridge",
                        ipam=ipam_config,
                        internal=False,
                        labels={"redteam": "true"},
                    )
                    logger.info(f"Created isolated network: {self.bridge_name}")
            except Exception as e:
                logger.warning(f"Failed to create network: {e}")
    
    def create_container(
        self,
        config: Optional[ContainerConfig] = None,
        name: Optional[str] = None,
    ) -> str:
        """Create a new sandbox container."""
        if not self.client:
            raise RuntimeError("Docker client not available")
        
        config = config or ContainerConfig()
        container_name = name or f"{self.container_prefix}-{uuid4().hex[:8]}"
        
        binds = {}
        for vol in self.volumes_config + (config.volumes or []):
            if vol.get("type") == "bind":
                binds[vol["source"]] = {"bind": vol["target"], "mode": "ro" if vol.get("read_only") else "rw"}
            elif vol.get("type") == "volume":
                binds[vol["name"]] = {"bind": vol["target"], "mode": "rw"}
        
        try:
            container = self.client.containers.create(
                image=config.image or self.image,
                name=container_name,
                command=config.command,
                working_dir=config.working_dir,
                user=config.user,
                environment=config.environment,
                network_mode=config.network_mode or self.network_mode,
                volumes=binds if binds else None,
                nano_cpus=int(self.cpu_count * 1e9),
                mem_limit=self.memory_limit,
                pids_limit=self.pids_limit,
                privileged=config.privileged,
                cap_add=config.cap_add or ["NET_ADMIN", "NET_RAW"],
                cap_drop=config.cap_drop or ["ALL"],
                log_config=LogConfig(type="json-file", config={"max-size": "10m", "max-file": "3"}),
                stdin_open=True,
                tty=True,
                detach=True,
            )
            
            self.containers[container.id] = container
            logger.info(f"Created container: {container_name} ({container.id})")
            return container.id
            
        except Exception as e:
            logger.error(f"Failed to create container: {e}")
            raise
    
    def start_container(self, container_id: str) -> bool:
        """Start a container."""
        if not self.client:
            return False
        try:
            container = self.client.containers.get(container_id)
            container.start()
            time.sleep(2)
            self._install_essential_tools(container)
            logger.info(f"Started container: {container_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to start container: {e}")
            return False
    
    def _install_essential_tools(self, container: Container) -> None:
        """Install essential security tools in container."""
        try:
            commands = [
                "apt-get update -qq",
                "apt-get install -y -qq nmap nikto sqlmap gobuster curl wget git",
            ]
            for cmd in commands:
                exit_code, output = container.exec_run(cmd, demux=True)
                if exit_code != 0:
                    logger.warning(f"Tool installation warning: {output[1].decode() if output[1] else ''}")
            logger.debug("Essential tools installed")
        except Exception as e:
            logger.warning(f"Failed to install tools: {e}")
    
    def stop_container(self, container_id: str, timeout: int = 10) -> bool:
        """Stop a container."""
        if not self.client:
            return False
        try:
            container = self.client.containers.get(container_id)
            container.stop(timeout=timeout)
            logger.info(f"Stopped container: {container_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to stop container: {e}")
            return False
    
    def remove_container(self, container_id: str, force: bool = False) -> bool:
        """Remove a container."""
        if not self.client:
            return False
        try:
            container = self.client.containers.get(container_id)
            container.remove(force=force)
            self.containers.pop(container_id, None)
            self.snapshots.pop(container_id, None)
            logger.info(f"Removed container: {container_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove container: {e}")
            return False
    
    def execute_command(
        self,
        container_id: str,
        command: str,
        workdir: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None,
        timeout: int = 300,
    ) -> tuple[int, str, str]:
        """Execute command in container."""
        if not self.client:
            return -1, "", "Docker client not available"
        try:
            container = self.client.containers.get(container_id)
            exec_instance = container.exec_run(command, workdir=workdir, environment=environment, demux=True, socket=False)
            stdout = exec_instance.output[0].decode() if exec_instance.output and exec_instance.output[0] else ""
            stderr = exec_instance.output[1].decode() if exec_instance.output and len(exec_instance.output) > 1 and exec_instance.output[1] else ""
            return exec_instance.exit_code, stdout, stderr
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return -1, "", str(e)
    
    def create_snapshot(self, container_id: str, description: Optional[str] = None) -> Optional[str]:
        """Create a snapshot of a container."""
        if not self.client:
            return None
        try:
            container = self.client.containers.get(container_id)
            snapshot_image = container.commit(repository=f"{self.container_prefix}-snapshot", tag=f"{uuid4().hex[:8]}")
            snapshot_id = snapshot_image.id
            self.snapshots[container_id] = SnapshotInfo(snapshot_id=snapshot_id, container_id=container_id, description=description)
            logger.info(f"Created snapshot: {snapshot_id} for container {container_id}")
            return snapshot_id
        except Exception as e:
            logger.error(f"Failed to create snapshot: {e}")
            return None
    
    def restore_snapshot(self, container_id: str, snapshot_id: Optional[str] = None) -> bool:
        """Restore container from snapshot."""
        if not self.client:
            return False
        try:
            if snapshot_id is None:
                snapshot_info = self.snapshots.get(container_id)
                if not snapshot_info:
                    logger.error(f"No snapshot found for container {container_id}")
                    return False
                snapshot_id = snapshot_info.snapshot_id
            
            snapshot_image = self.client.images.get(snapshot_id)
            self.stop_container(container_id)
            
            old_container = self.client.containers.get(container_id)
            old_config = old_container.attrs["Config"]
            old_container.remove(force=True)
            
            new_container = self.client.containers.create(
                image=snapshot_image.id,
                name=old_container.name,
                command=old_config.get("Cmd"),
                working_dir=old_config.get("WorkingDir"),
                environment=old_config.get("Env"),
                network_mode=self.network_mode,
                stdin_open=True,
                tty=True,
                detach=True,
            )
            
            self.containers.pop(container_id, None)
            self.containers[new_container.id] = new_container
            self.start_container(new_container.id)
            
            logger.info(f"Restored container {container_id} from snapshot {snapshot_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to restore snapshot: {e}")
            return False
    
    def get_container_logs(self, container_id: str, tail: int = 100, since: Optional[datetime] = None) -> str:
        """Get container logs."""
        if not self.client:
            return ""
        try:
            container = self.client.containers.get(container_id)
            kwargs = {"tail": tail}
            if since:
                kwargs["since"] = since.isoformat()
            logs = container.logs(**kwargs)
            return logs.decode() if isinstance(logs, bytes) else logs
        except Exception as e:
            logger.error(f"Failed to get logs: {e}")
            return ""
    
    def get_container_stats(self, container_id: str) -> Dict[str, Any]:
        """Get container resource usage stats."""
        if not self.client:
            return {}
        try:
            container = self.client.containers.get(container_id)
            stats = container.stats(stream=False)
            return {
                "cpu_percent": self._calculate_cpu_percent(stats),
                "memory_usage": stats.get("memory_stats", {}).get("usage", 0),
                "memory_limit": stats.get("memory_stats", {}).get("limit", 0),
                "network_rx": sum(v.get("rx_bytes", 0) for v in stats.get("networks", {}).values()),
                "network_tx": sum(v.get("tx_bytes", 0) for v in stats.get("networks", {}).values()),
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}
    
    def _calculate_cpu_percent(self, stats: Dict[str, Any]) -> float:
        """Calculate CPU percentage from stats."""
        cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        system_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
        if system_delta > 0:
            return (cpu_delta / system_delta) * stats["cpu_stats"]["online_cpus"] * 100
        return 0.0
    
    def health_check(self, container_id: str) -> bool:
        """Check if container is healthy."""
        if not self.client:
            return False
        try:
            container = self.client.containers.get(container_id)
            if container.status != "running":
                return False
            exit_code, _, _ = self.execute_command(container_id, "echo health")
            return exit_code == 0
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def list_containers(self, all: bool = False) -> List[Dict[str, Any]]:
        """List managed containers."""
        if not self.client:
            return []
        try:
            containers = self.client.containers.list(all=all)
            return [
                {"id": c.id, "name": c.name, "status": c.status, "image": c.image.tags[0] if c.image.tags else c.image.short_id, "created": c.attrs["Created"]}
                for c in containers
                if self.container_prefix in c.name
            ]
        except Exception as e:
            logger.error(f"Failed to list containers: {e}")
            return []
    
    def cleanup(self, force: bool = False) -> None:
        """Clean up all managed containers and networks."""
        if not self.client:
            return
        for container_id in list(self.containers.keys()):
            try:
                self.remove_container(container_id, force=force)
            except Exception as e:
                logger.error(f"Failed to remove container during cleanup: {e}")
        for snapshot_info in self.snapshots.values():
            try:
                self.client.images.remove(snapshot_info.snapshot_id, force=True)
            except Exception as e:
                logger.error(f"Failed to remove snapshot: {e}")
        try:
            network = self.client.networks.get(self.bridge_name)
            network.remove()
        except Exception:
            pass
        self.containers.clear()
        self.snapshots.clear()
        logger.info("DockerSandboxManager cleanup completed")
