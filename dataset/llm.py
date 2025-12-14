"""
Universal LLM client for the DATE-SMT dataset generation.

This module provides a generic LLM interface that can be used by any dataset generator.
"""

import json
import os
import re
from typing import Optional, Any

try:
    from dotenv import load_dotenv
    import pathlib
    # Load .env file from project root
    load_dotenv()
    # Also try relative to this file
    script_path = pathlib.Path(__file__).resolve()
    repo_root = script_path.parent
    env_path = repo_root / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)
except ImportError:
    # dotenv not available, skip loading .env file
    pass

# ============================================================================
# CONFIGURATION: Enable/Disable LLM Providers
# ============================================================================
# Set these flags to control which providers are available for auto-detection
# When both are enabled, Anthropic is preferred by default
ENABLE_OPENAI = False
ENABLE_ANTHROPIC = True

# Provider configuration - centralized metadata
PROVIDER_CONFIG = {
    "openai": {
        "enabled": ENABLE_OPENAI,
        "default_model": "gpt-5.1",
        "api_key_env": "OPENAI_API_KEY",
        "thinking_param": "reasoning_effort",
        "thinking_value": "high",
    },
    "anthropic": {
        "enabled": ENABLE_ANTHROPIC,
        "default_model": "claude-4-5-sonnet-latest",
        "api_key_env": "ANTHROPIC_API_KEY",
        "thinking_param": "thinking",
        "thinking_value": {"type": "enabled", "budget_tokens": 10000},
    },
}


def _strip_code_fences(s: str) -> str:
    """Handle ```json ... ``` or ``` ... ``` blocks gracefully."""
    if "```" not in s:
        return s.strip()
    # Prefer explicitly tagged json fence
    m = re.search(r"```json\s*(.*?)```", s, flags=re.S)
    if m:
        return m.group(1).strip()
    # Fallback: first fenced block
    m = re.search(r"```(.*?)```", s, flags=re.S)
    return m.group(1).strip() if m else s.strip()


def _normalize_llm_json(s: str) -> str:
    """Best-effort normalization to improve JSON parse success without altering content semantics.

    - Strip BOM/whitespace
    - Replace curly/smart quotes with ASCII quotes
    - Normalize line endings
    - Ensure backticks are removed
    """
    if not isinstance(s, str):
        return s
    txt = s.strip().lstrip("\ufeff")
    # Remove stray backtick fences if any slipped through
    txt = txt.replace("```", "")
    # Normalize fancy quotes to plain quotes
    smart_double = "\u201c\u201d\uFF02"
    smart_single = "\u2018\u2019\uFF07"
    for ch in smart_double:
        txt = txt.replace(ch, '"')
    for ch in smart_single:
        txt = txt.replace(ch, "'")
    # Normalize line endings
    txt = txt.replace("\r\n", "\n").replace("\r", "\n")
    return txt


def _extract_json_array(s: str) -> str:
    """Greedy substring extraction of the first plausible JSON array."""
    start = s.find('[')
    end = s.rfind(']')
    if start != -1 and end != -1 and end > start:
        return s[start : end + 1]
    raise ValueError("No JSON array found in response.")


def _detect_provider_and_model() -> tuple[str, str]:
    """Auto-detect provider and return appropriate model based on enabled providers."""
    # Get available providers with API keys
    available_providers = {}
    for provider_name, config in PROVIDER_CONFIG.items():
        if config["enabled"]:
            api_key = os.getenv(config["api_key_env"])
            if api_key:
                available_providers[provider_name] = config

    # Check if at least one provider is enabled
    enabled_count = sum(1 for config in PROVIDER_CONFIG.values() if config["enabled"])
    if enabled_count == 0:
        raise ValueError(
            "No LLM providers enabled. Set ENABLE_OPENAI or ENABLE_ANTHROPIC to True in llm.py."
        )

    # Return first available provider (prefer Anthropic if both available)
    if "anthropic" in available_providers:
        return "anthropic", available_providers["anthropic"]["default_model"]
    elif "openai" in available_providers:
        return "openai", available_providers["openai"]["default_model"]
    else:
        # No API keys found for enabled providers
        enabled_keys = [
            config["api_key_env"]
            for config in PROVIDER_CONFIG.values()
            if config["enabled"]
        ]
        raise ValueError(
            f"No API key found for enabled providers. Please set: {', '.join(enabled_keys)}"
        )


class LLMClient:
    """Universal LLM client supporting OpenAI and Anthropic APIs."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        provider: str = "auto",
        enable_thinking: bool = True,
    ):
        """
        Initialize LLM client.

        Args:
            api_key: API key for the provider (overrides environment variable)
            model: Model name (uses default for provider if not specified)
            provider: Provider name - 'openai', 'anthropic', or 'auto' (default: 'auto')
            enable_thinking: Enable maximum thinking/reasoning capability (default: True)
        """
        self.api_key = api_key
        self.provider = provider.lower()
        self.enable_thinking = enable_thinking

        # Auto-detect provider and model if not specified
        if self.provider == "auto":
            self.provider, default_model = _detect_provider_and_model()
            self.model = model or default_model
        else:
            # Provider explicitly specified - validate and configure
            if self.provider not in PROVIDER_CONFIG:
                raise ValueError(
                    f"Unsupported provider: {provider}. Use 'openai', 'anthropic', or 'auto'."
                )

            config = PROVIDER_CONFIG[self.provider]
            if not config["enabled"]:
                raise ValueError(
                    f"{self.provider.capitalize()} provider is disabled. "
                    f"Set ENABLE_{self.provider.upper()} = True in llm.py to enable it."
                )

            self.api_key = api_key or os.getenv(config["api_key_env"])
            if not self.api_key:
                raise ValueError(
                    f"{self.provider.capitalize()} API key required. "
                    f"Set {config['api_key_env']} or pass api_key."
                )

            self.model = model or config["default_model"]

        # Set up the appropriate client
        if self.provider == "openai":
            import openai

            self.client = openai.OpenAI(api_key=self.api_key)
        elif self.provider == "anthropic":
            import anthropic

            self.client = anthropic.Anthropic(api_key=self.api_key)

        # Light defaults that usually help JSON fidelity
        self.max_tokens = 2000
        self.temperature = 0.4
        self.top_p = 0.95

    def call(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Make a call to the LLM API.

        Args:
            system_prompt: System prompt for the LLM
            user_prompt: User prompt for the LLM
            temperature: Temperature setting (uses instance default if not specified)
            max_tokens: Maximum tokens (uses instance default if not specified)

        Returns:
            Response text from the LLM
        """
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens

        if self.provider == "openai":
            return self._call_openai(system_prompt, user_prompt, temp, tokens)
        elif self.provider == "anthropic":
            return self._call_anthropic(system_prompt, user_prompt, temp, tokens)

    def _call_openai(
        self, system_prompt: str, user_prompt: str, temperature: float, max_tokens: int
    ) -> str:
        """Make an API call to OpenAI."""
        api_params = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "top_p": self.top_p,
            "max_tokens": max_tokens,
        }

        # Add thinking/reasoning parameters
        if self.enable_thinking:
            config = PROVIDER_CONFIG["openai"]
            api_params[config["thinking_param"]] = config["thinking_value"]

        resp = self.client.chat.completions.create(**api_params)
        return resp.choices[0].message.content

    def _call_anthropic(
        self, system_prompt: str, user_prompt: str, temperature: float, max_tokens: int
    ) -> str:
        """Make an API call to Anthropic."""
        api_params = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": f"{system_prompt}\n",
            "messages": [{"role": "user", "content": user_prompt}],
        }

        # Add thinking/reasoning parameters
        if self.enable_thinking:
            config = PROVIDER_CONFIG["anthropic"]
            api_params[config["thinking_param"]] = config["thinking_value"]

        resp = self.client.messages.create(**api_params)
        return resp.content[0].text

    def parse_json_response(self, response: str, extract_array: bool = False) -> any:
        """
        Parse JSON from LLM response with normalization and error recovery.

        Args:
            response: Raw response from LLM
            extract_array: If True, try to extract JSON array from response

        Returns:
            Parsed JSON object

        Raises:
            ValueError: If JSON parsing fails
        """
        txt = _strip_code_fences(response)
        normalized = _normalize_llm_json(txt)

        if extract_array:
            try:
                # Try parsing directly first
                return json.loads(normalized)
            except json.JSONDecodeError:
                # Try extracting array
                extracted = _extract_json_array(normalized)
                return json.loads(_normalize_llm_json(extracted))
        else:
            return json.loads(normalized)
