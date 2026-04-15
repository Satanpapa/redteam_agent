"""Tests for Docker Sandbox module."""

import pytest
from unittest.mock import Mock, patch
from code.docker_sandbox import DockerSandboxManager
from code.models import ContainerConfig


class TestDockerSandboxManager:
    """Test cases for DockerSandboxManager."""

    @patch("docker.from_env")
    def test_initialization(self, mock_docker):
        """Test sandbox manager initializes correctly."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_docker.return_value = mock_client
        
        manager = DockerSandboxManager()
        
        assert manager.client is not None
        assert manager.image == "kalilinux/kali-rolling:latest"

    @patch("docker.from_env")
    def test_create_container(self, mock_docker):
        """Test container creation."""
        mock_client = Mock()
        mock_container = Mock()
        mock_container.id = "test-container-id"
        mock_client.containers.create.return_value = mock_container
        mock_docker.return_value = mock_client
        
        manager = DockerSandboxManager()
        manager.client = mock_client
        
        container_id = manager.create_container(
            name="test-container"
        )
        
        assert container_id == "test-container-id"
        assert container_id in manager.containers

    @patch("docker.from_env")
    def test_start_container(self, mock_docker):
        """Test container start."""
        mock_client = Mock()
        mock_container = Mock()
        mock_client.containers.get.return_value = mock_container
        mock_docker.return_value = mock_client
        
        manager = DockerSandboxManager()
        manager.client = mock_client
        manager.containers["test-id"] = mock_container
        
        result = manager.start_container("test-id")
        
        assert result is True
        mock_container.start.assert_called_once()

    @patch("docker.from_env")
    def test_stop_container(self, mock_docker):
        """Test container stop."""
        mock_client = Mock()
        mock_container = Mock()
        mock_client.containers.get.return_value = mock_container
        mock_docker.return_value = mock_client
        
        manager = DockerSandboxManager()
        manager.client = mock_client
        
        result = manager.stop_container("test-id")
        
        assert result is True
        mock_container.stop.assert_called_once()

    @patch("docker.from_env")
    def test_execute_command(self, mock_docker):
        """Test command execution in container."""
        mock_client = Mock()
        mock_container = Mock()
        mock_exec = Mock()
        mock_exec.exit_code = 0
        mock_exec.output = (b"output", b"")
        mock_container.exec_run.return_value = mock_exec
        mock_client.containers.get.return_value = mock_container
        mock_docker.return_value = mock_client
        
        manager = DockerSandboxManager()
        manager.client = mock_client
        
        exit_code, stdout, stderr = manager.execute_command(
            "test-id", "ls -la"
        )
        
        assert exit_code == 0
        assert stdout == "output"

    @patch("docker.from_env")
    def test_health_check(self, mock_docker):
        """Test container health check."""
        mock_client = Mock()
        mock_container = Mock()
        mock_container.status = "running"
        mock_client.containers.get.return_value = mock_container
        mock_docker.return_value = mock_client
        
        manager = DockerSandboxManager()
        manager.client = mock_client
        
        # Mock execute_command to return success
        manager.execute_command = Mock(return_value=(0, "", ""))
        
        result = manager.health_check("test-id")
        
        assert result is True

    @patch("docker.from_env")
    def test_list_containers(self, mock_docker):
        """Test listing containers."""
        mock_client = Mock()
        mock_container = Mock()
        mock_container.id = "container1"
        mock_container.name = "redteam-sandbox-test"
        mock_container.status = "running"
        mock_container.image.tags = ["kali:latest"]
        mock_container.attrs = {"Created": "2024-01-01"}
        mock_client.containers.list.return_value = [mock_container]
        mock_docker.return_value = mock_client
        
        manager = DockerSandboxManager()
        manager.client = mock_client
        
        containers = manager.list_containers()
        
        assert len(containers) == 1
        assert containers[0]["name"] == "redteam-sandbox-test"

    @patch("docker.from_env")
    def test_cleanup(self, mock_docker):
        """Test cleanup of all resources."""
        mock_client = Mock()
        mock_docker.return_value = mock_client
        
        manager = DockerSandboxManager()
        manager.client = mock_client
        manager.containers["test-id"] = Mock()
        
        manager.cleanup(force=True)
        
        assert len(manager.containers) == 0
        assert len(manager.snapshots) == 0
