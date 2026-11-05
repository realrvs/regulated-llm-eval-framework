"""Base adapter protocol for LLM providers.

Covers FR-003, NFR-008.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LLMRequest:
    """Request to send to an LLM provider."""

    prompt: str
    model: str = ""
    temperature: float = 0.0
    max_tokens: int = 1024
    stop_sequences: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class LLMResponse:
    """Response from an LLM provider."""

    text: str
    model: str = ""
    tokens_input: int = 0
    tokens_output: int = 0
    finish_reason: str = ""
    latency_ms: float = 0.0
    error: str | None = None


class BaseAdapter(ABC):
    """Abstract base class for LLM provider adapters.

    All adapters must implement:
    - generate(): Send a prompt and return a response
    - cost(): Estimate cost for a request
    - provider(): Return the provider name
    """

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Send a prompt to the LLM and return the response.

        Args:
            request: LLM request with prompt, model, etc.

        Returns:
            LLMResponse with text, tokens, latency, etc.

        Raises:
            RateLimitExhausted: If all retry attempts are exhausted.
            MissingCredentials: If API key is not set.
        """

    @abstractmethod
    def provider(self) -> str:
        """Return the provider name (e.g. 'yandexgpt', 'gigachat')."""

    @abstractmethod
    def model_name(self) -> str:
        """Return the model name being used."""

    def estimate_cost(self, tokens_input: int, tokens_output: int) -> float | None:
        """Estimate cost in RUB for the given token counts.

        Override in subclasses with provider-specific pricing.
        Returns None if pricing is not configured.
        """
        return None

    @property
    def is_foreign(self) -> bool:
        """Whether this adapter connects to a foreign (non-Russian) provider.

        Used for 152-FZ compliance (NFR-SEC-001).
        """
        return False
