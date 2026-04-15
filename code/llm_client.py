"""Ollama OpenAI-compatible client with retries and streaming support."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    base_url: str
    api_key: str
    planner_model: str
    analyzer_model: str
    embed_model: str
    timeout_seconds: int = 120
    max_retries: int = 3


class OllamaClient:
    def __init__(self, config: LLMConfig):
        self.config = config
        self.planner = ChatOpenAI(
            model=config.planner_model,
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout_seconds,
            temperature=0.2,
        )
        self.analyzer = ChatOpenAI(
            model=config.analyzer_model,
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout_seconds,
            temperature=0.1,
        )
        self.embedder = OpenAIEmbeddings(
            model=config.embed_model,
            api_key=config.api_key,
            base_url=config.base_url,
        )

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def plan(self, prompt: str) -> str:
        logger.debug("Planner prompt length=%d", len(prompt))
        return self.planner.invoke(prompt).content

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def analyze(self, prompt: str) -> str:
        return self.analyzer.invoke(prompt).content

    def stream_plan(self, prompt: str) -> Iterable[str]:
        for chunk in self.planner.stream(prompt):
            if chunk.content:
                yield chunk.content

    def embed(self, text: str) -> list[float]:
        return self.embedder.embed_query(text)
