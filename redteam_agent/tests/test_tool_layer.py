"""Tests for Tool Layer module."""

import pytest
from code.tool_layer import OutputNormalizer, DataEnricher, ToolRegistry


class TestOutputNormalizer:
    """Test cases for OutputNormalizer."""

    def test_initialization(self):
        """Test normalizer initializes correctly."""
        normalizer = OutputNormalizer()
        assert normalizer.patterns is not None

    def test_normalize_nmap(self):
        """Test nmap output normalization."""
        normalizer = OutputNormalizer()
        
        output = """
Nmap scan report for 192.168.1.100
Host is up.
PORT    STATE SERVICE VERSION
21/tcp  open  ftp     vsftpd 3.0.3
80/tcp  open  http    Apache httpd 2.4.41
        """
        
        normalized = normalizer.normalize_nmap(output)
        
        assert "targets" in normalized
        assert len(normalized["targets"]) > 0

    def test_normalize_gobuster(self):
        """Test gobuster output normalization."""
        normalizer = OutputNormalizer()
        
        output = """
/admin (Status: 301)
/login (Status: 200)
/assets/ (Status: 301)
        """
        
        normalized = normalizer.normalize_gobuster(output)
        
        assert "directories" in normalized or "files" in normalized

    def test_normalize_generic(self):
        """Test generic normalization."""
        normalizer = OutputNormalizer()
        
        output = "Found CVE-2021-44228 on 192.168.1.100:8080"
        
        normalized = normalizer.normalize_generic(output)
        
        assert "cves" in normalized
        assert len(normalized["cves"]) > 0


class TestDataEnricher:
    """Test cases for DataEnricher."""

    def test_initialization(self):
        """Test enricher initializes correctly."""
        enricher = DataEnricher()
        assert enricher.CVE_DATABASE is not None

    def test_enrich_target(self):
        """Test target enrichment."""
        from code.models import TargetInfo, ServiceInfo
        
        enricher = DataEnricher()
        
        target = TargetInfo(
            address="192.168.1.100",
            services=[
                ServiceInfo(
                    port=445,
                    service_name="microsoft-ds",
                    version="Windows Server 2008",
                )
            ],
        )
        
        enriched = enricher.enrich_target(target)
        
        # Should find EternalBlue vulnerability
        assert len(enriched.vulnerabilities) > 0

    def test_correlate_findings(self):
        """Test finding correlation across targets."""
        from code.models import TargetInfo, Vulnerability, RiskLevel
        
        enricher = DataEnricher()
        
        targets = [
            TargetInfo(address="192.168.1.100"),
            TargetInfo(address="192.168.1.101"),
        ]
        
        # Add same vulnerability to both
        vuln = Vulnerability(
            cve_id="CVE-2021-44228",
            name="Log4Shell",
            description="Test",
            severity=RiskLevel.CRITICAL,
        )
        targets[0].vulnerabilities.append(vuln)
        targets[1].vulnerabilities.append(vuln)
        
        correlation = enricher.correlate_findings(targets)
        
        assert "common_vulnerabilities" in correlation


class TestToolRegistry:
    """Test cases for ToolRegistry."""

    def test_list_tools(self):
        """Test listing registered tools."""
        tools = ToolRegistry.list_tools()
        
        assert len(tools) > 0
        assert any(t["name"] == "nmap" for t in tools)

    def test_get_tool(self):
        """Test getting a tool by name."""
        tool = ToolRegistry.get("nmap")
        
        assert tool is not None
        assert tool.name == "nmap"

    def test_get_unknown_tool(self):
        """Test getting unknown tool returns None."""
        tool = ToolRegistry.get("nonexistent_tool")
        
        assert tool is None
