"""
Universal LLM client for the DATE-SMT dataset generation.

Supports both OpenAI and Anthropic APIs with robust JSON parsing and normalization.
This module provides a generic LLM interface that can be used by any dataset generator.
"""

import json
import os
import re
from typing import Optional, Dict, List, Any

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

# Default models for each provider
DEFAULT_OPENAI_MODEL = "gpt-3.5-turbo"
DEFAULT_ANTHROPIC_MODEL = "claude-3-7-sonnet-latest"


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
    """Auto-detect provider and return appropriate model."""
    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    if anthropic_key and not openai_key:
        return "anthropic", DEFAULT_ANTHROPIC_MODEL
    elif openai_key and not anthropic_key:
        return "openai", DEFAULT_OPENAI_MODEL
    elif anthropic_key and openai_key:
        # Both available, prefer Anthropic
        return "anthropic", DEFAULT_ANTHROPIC_MODEL
    else:
        raise ValueError(
            "No API key found. Set OPENAI_API_KEY or ANTHROPIC_API_KEY environment variable, or pass api_key parameter."
        )


class LLMClient:
    """Universal LLM client supporting OpenAI and Anthropic APIs."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        provider: str = "auto",
    ):
        """
        Initialize LLM client.

        Args:
            api_key: API key for the provider (overrides environment variable)
            model: Model name (uses default for provider if not specified)
            provider: Provider name - 'openai', 'anthropic', or 'auto' (default: 'auto')
        """
        self.api_key = api_key
        self.provider = provider.lower()

        # Auto-detect provider and model if not specified
        if self.provider == "auto":
            self.provider, default_model = _detect_provider_and_model()
            self.model = model or default_model
        else:
            # Provider explicitly specified
            if self.provider == "openai":
                self.api_key = api_key or os.getenv("OPENAI_API_KEY")
                if not self.api_key:
                    raise ValueError(
                        "OpenAI API key required. Set OPENAI_API_KEY or pass api_key."
                    )
                self.model = model or DEFAULT_OPENAI_MODEL
            elif self.provider == "anthropic":
                self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
                if not self.api_key:
                    raise ValueError(
                        "Anthropic API key required. Set ANTHROPIC_API_KEY or pass api_key."
                    )
                self.model = model or DEFAULT_ANTHROPIC_MODEL
            else:
                raise ValueError(
                    f"Unsupported provider: {provider}. Use 'openai', 'anthropic', or 'auto'."
                )

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
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "system",
                        "content": "When randomness is needed, use a deterministic seed of 1337.",
                    },
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temp,
                top_p=self.top_p,
                max_tokens=tokens,
            )
            return resp.choices[0].message.content
        elif self.provider == "anthropic":
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=tokens,
                temperature=temp,
                system=system_prompt
                + "\n\nWhen randomness is needed, use a deterministic seed of 1337.",
                messages=[{"role": "user", "content": user_prompt}],
            )
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


class LLMPipeline:
    """
    Lightweight helper for multi-step LLM calls with conversation history.

    This is not a full tool-using agent, just a thin wrapper around LLMClient
    that tracks history and provides a JSON-parsing helper.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        provider: str = "auto",
    ):
        self.llm_client = LLMClient(api_key=api_key, model=model, provider=provider)
        self.conversation_history: List[Dict[str, str]] = []
        self.call_count = 0

    def reset(self) -> None:
        """Reset conversation history and call counter."""
        self.conversation_history = []
        self.call_count = 0

    def call(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        include_history: bool = True,
    ) -> str:
        """Call the LLM, optionally including previous exchanges as history."""
        self.call_count += 1

        if include_history and self.conversation_history:
            history_text = "\n\n".join(
                [
                    f"Previous exchange {i+1}:\nUser: {ex['user']}\nAssistant: {ex['assistant']}"
                    for i, ex in enumerate(self.conversation_history)
                ]
            )
            full_user_prompt = f"{history_text}\n\nCurrent request:\n{user_prompt}"
        else:
            full_user_prompt = user_prompt

        response = self.llm_client.call(
            system_prompt=system_prompt,
            user_prompt=full_user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        self.conversation_history.append(
            {
                "user": user_prompt,
                "assistant": response,
            }
        )

        return response

    def call_with_json_output(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        include_history: bool = True,
    ) -> Optional[dict]:
        """Call the LLM and parse the response as JSON."""
        response = self.call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            include_history=include_history,
        )
        try:
            return self.llm_client.parse_json_response(response)
        except (json.JSONDecodeError, ValueError, Exception):
            return None

    def get_call_count(self) -> int:
        """Number of calls made in the current run."""
        return self.call_count

    def get_history(self) -> List[Dict[str, str]]:
        """Return a copy of the conversation history."""
        return self.conversation_history.copy()

