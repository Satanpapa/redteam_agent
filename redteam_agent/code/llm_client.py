"""
LLM Client for Red Team Agent v2.0

Ollama wrapper with retry logic, streaming support, and OpenAI-compatible API.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional
from uuid import uuid4

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .models import LLMMessage, LLMResponse

logger = logging.getLogger(__name__)


class OllamaClient:
    """
    Ollama client with OpenAI-compatible API.
    
    Features:
    - Retry with exponential backoff
    - Streaming support
    - Connection pooling
    - Comprehensive error handling
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        model: str = "qwen2.5-coder:32b",
        embedding_model: str = "nomic-embed-text",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: int = 120,
        max_retries: int = 3,
    ):
        """
        Initialize Ollama client.
        
        Args:
            base_url: Ollama API base URL
            model: Default model for completions
            embedding_model: Model for embeddings
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.embedding_model = embedding_model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        
        # HTTP client with connection pooling
        self._client: Optional[httpx.AsyncClient] = None
        
        # Retry configuration
        self.max_retries = max_retries
        
        logger.info(f"OllamaClient initialized: {base_url} ({model})")
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                limits=httpx.Limits(max_keepalive_connections=10),
            )
        return self._client
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> LLMResponse:
        """
        Send chat completion request.
        
        Args:
            messages: List of message dictionaries
            model: Model to use (overrides default)
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            stream: Whether to stream response
            
        Returns:
            LLMResponse object
        """
        client = await self._get_client()
        
        start_time = time.time()
        
        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature or self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
            "stream": stream,
        }
        
        try:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
            )
            response.raise_for_status()
            
            data = response.json()
            
            latency_ms = (time.time() - start_time) * 1000
            
            return LLMResponse(
                content=data["choices"][0]["message"]["content"],
                model=data.get("model", self.model),
                usage=data.get("usage", {}),
                finish_reason=data["choices"][0].get("finish_reason"),
                latency_ms=latency_ms,
            )
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            raise
        except Exception as e:
            logger.error(f"Chat completion error: {e}")
            raise
    
    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat completion.
        
        Args:
            messages: List of message dictionaries
            model: Model to use
            temperature: Sampling temperature
            
        Yields:
            Response chunks
        """
        client = await self._get_client()
        
        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature or self.temperature,
            "stream": True,
        }
        
        try:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=payload,
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        
                        import json
                        try:
                            chunk = json.loads(data)
                            content = chunk["choices"][0]["delta"].get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
                            
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            raise
    
    async def embed(self, text: str, model: Optional[str] = None) -> List[float]:
        """
        Generate embeddings.
        
        Args:
            text: Text to embed
            model: Embedding model
            
        Returns:
            Embedding vector
        """
        client = await self._get_client()
        
        payload = {
            "model": model or self.embedding_model,
            "input": text,
        }
        
        try:
            response = await client.post(
                f"{self.base_url}/embeddings",
                json=payload,
            )
            response.raise_for_status()
            
            data = response.json()
            return data["data"][0]["embedding"]
            
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            raise
    
    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Generate completion for a prompt.
        
        Args:
            prompt: User prompt
            system: Optional system message
            model: Model to use
            **kwargs: Additional parameters
            
        Returns:
            LLMResponse object
        """
        messages = []
        
        if system:
            messages.append({"role": "system", "content": system})
        
        messages.append({"role": "user", "content": prompt})
        
        return await self.chat(messages, model=model, **kwargs)
    
    async def list_models(self) -> List[Dict[str, Any]]:
        """List available models."""
        client = await self._get_client()
        
        try:
            response = await client.get(f"{self.base_url}/models")
            response.raise_for_status()
            
            data = response.json()
            return data.get("data", [])
            
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []
    
    async def health_check(self) -> bool:
        """Check if Ollama service is healthy."""
        client = await self._get_client()
        
        try:
            response = await client.get(f"{self.base_url}/models")
            return response.status_code == 200
        except Exception:
            return False
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


class LLMOrchestrator:
    """
    High-level LLM orchestrator for agent operations.
    
    Provides specialized methods for planning, analysis, and decision-making.
    """
    
    def __init__(self, client: OllamaClient):
        """
        Initialize LLM orchestrator.
        
        Args:
            client: OllamaClient instance
        """
        self.client = client
        
        # System prompts for different roles
        self.system_prompts = {
            "planner": """You are an expert penetration testing planner.
Your task is to analyze the current state and plan the next actions.

Guidelines:
- Be methodical and systematic
- Prioritize low-risk, high-reward actions
- Consider stealth and detection avoidance
- Build on previous findings
- Suggest specific tools and commands""",
            
            "analyzer": """You are a security analysis expert.
Analyze tool outputs and identify:
- Discovered hosts and services
- Potential vulnerabilities
- Attack vectors
- Credential opportunities
- Next steps for exploitation""",
            
            "decision": """You are a red team decision advisor.
Evaluate potential actions based on:
- Success probability
- Impact
- Stealth
- Resource cost
- Risk level

Provide clear recommendations.""",
        }
    
    async def plan_next_action(
        self,
        current_state: Dict[str, Any],
        action_history: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Plan the next action using LLM.
        
        Args:
            current_state: Current engagement state
            action_history: Previous actions taken
            
        Returns:
            Planned action dictionary
        """
        prompt = self._build_planning_prompt(current_state, action_history)
        
        response = await self.client.generate(
            prompt=prompt,
            system=self.system_prompts["planner"],
            temperature=0.7,
        )
        
        # Parse response into structured action
        return self._parse_planning_response(response.content)
    
    async def analyze_results(
        self,
        tool_output: str,
        tool_name: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Analyze tool output using LLM.
        
        Args:
            tool_output: Raw tool output
            tool_name: Name of the tool
            context: Additional context
            
        Returns:
            Analysis results
        """
        prompt = f"""Analyze the following {tool_name} output:

{tool_output}

Context: {context}

Provide:
1. Key findings
2. Identified vulnerabilities
3. Recommended follow-up actions
4. Risk assessment"""
        
        response = await self.client.generate(
            prompt=prompt,
            system=self.system_prompts["analyzer"],
        )
        
        return {
            "analysis": response.content,
            "findings": self._extract_findings(response.content),
        }
    
    async def evaluate_action(
        self,
        action: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, float]:
        """
        Evaluate an action's metrics using LLM.
        
        Args:
            action: Action to evaluate
            context: Current context
            
        Returns:
            Metrics dictionary
        """
        prompt = f"""Evaluate this action:

Action: {action}
Context: {context}

Rate each metric from 0.0 to 1.0:
- success_probability
- impact
- stealth
- speed
- resource_cost
- risk

Respond with JSON format."""
        
        response = await self.client.generate(
            prompt=prompt,
            system=self.system_prompts["decision"],
        )
        
        return self._parse_metrics(response.content)
    
    def _build_planning_prompt(
        self,
        state: Dict[str, Any],
        history: List[Dict[str, Any]],
    ) -> str:
        """Build planning prompt from state and history."""
        prompt_parts = ["Current engagement state:"]
        
        # Add targets
        if state.get("discovered_targets"):
            prompt_parts.append("\nDiscovered targets:")
            for target in state["discovered_targets"]:
                prompt_parts.append(f"- {target.get('address')}: {target.get('services', [])}")
        
        # Add vulnerabilities
        if state.get("vulnerabilities"):
            prompt_parts.append("\nKnown vulnerabilities:")
            for vuln in state["vulnerabilities"]:
                prompt_parts.append(f"- {vuln.get('name')}: {vuln.get('severity')}")
        
        # Add recent actions
        if history:
            prompt_parts.append("\nRecent actions:")
            for action in history[-5:]:
                prompt_parts.append(f"- {action.get('action_name')}: {action.get('status')}")
        
        prompt_parts.append("\n\nWhat should be the next action? Provide specific tool and parameters.")
        
        return "\n".join(prompt_parts)
    
    def _parse_planning_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM planning response into structured action."""
        # Simple parsing - in production, use structured output
        action = {
            "name": "unknown",
            "tool": "unknown",
            "params": {},
            "reasoning": response,
        }
        
        # Try to extract tool name
        if "nmap" in response.lower():
            action["tool"] = "nmap"
            action["name"] = "port_scan"
        elif "nikto" in response.lower():
            action["tool"] = "nikto"
            action["name"] = "web_scan"
        
        return action
    
    def _extract_findings(self, analysis: str) -> List[Dict[str, Any]]:
        """Extract findings from analysis text."""
        findings = []
        
        # Simple extraction - in production, use NLP
        lines = analysis.split("\n")
        for line in lines:
            if any(keyword in line.lower() for keyword in ["vulnerability", "finding", "issue"]):
                findings.append({"description": line.strip()})
        
        return findings
    
    def _parse_metrics(self, response: str) -> Dict[str, float]:
        """Parse metrics from LLM response."""
        import json
        
        try:
            # Try to find JSON in response
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                metrics = json.loads(response[start:end])
                return {k: float(v) for k, v in metrics.items()}
        except Exception:
            pass
        
        # Default values
        return {
            "success_probability": 0.5,
            "impact": 0.5,
            "stealth": 0.5,
            "speed": 0.5,
            "resource_cost": 0.5,
            "risk": 0.5,
        }
