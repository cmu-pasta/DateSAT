"""
LLM Agent framework for multi-step reasoning tasks.

This module provides a simple agent framework that allows multiple LLM calls
with reasoning steps, conversation history, and structured outputs.
"""

import json
from typing import Dict, List, Optional, Any
from .llm import LLMClient


class LLMAgent:
    """
    Simple LLM agent that supports multi-step reasoning with conversation history.
    
    The agent maintains a conversation history and can make multiple calls
    to the LLM, allowing for reasoning, planning, and refinement steps.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        provider: str = "auto",
    ):
        """
        Initialize LLM agent.
        
        Args:
            api_key: API key for the LLM provider (overrides environment variable)
            model: Model name (uses default for provider if not specified)
            provider: Provider name - 'openai', 'anthropic', or 'auto' (default: 'auto')
        """
        self.llm_client = LLMClient(api_key=api_key, model=model, provider=provider)
        self.conversation_history: List[Dict[str, str]] = []
        self.call_count = 0
        
    def reset(self):
        """Reset conversation history."""
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
        """
        Make a call to the LLM with optional conversation history.
        
        Args:
            system_prompt: System prompt for this call
            user_prompt: User prompt for this call
            temperature: Temperature setting (uses client default if not specified)
            max_tokens: Maximum tokens (uses client default if not specified)
            include_history: Whether to include conversation history in the prompt
            
        Returns:
            Response text from the LLM
        """
        self.call_count += 1
        
        # Build full prompt with history if requested
        if include_history and self.conversation_history:
            history_text = "\n\n".join([
                f"Previous exchange {i+1}:\nUser: {ex['user']}\nAssistant: {ex['assistant']}"
                for i, ex in enumerate(self.conversation_history)
            ])
            full_user_prompt = f"{history_text}\n\nCurrent request:\n{user_prompt}"
        else:
            full_user_prompt = user_prompt
        
        # Make the call
        response = self.llm_client.call(
            system_prompt=system_prompt,
            user_prompt=full_user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        # Add to history
        self.conversation_history.append({
            "user": user_prompt,
            "assistant": response,
        })
        
        return response
    
    def call_with_json_output(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        include_history: bool = True,
    ) -> Optional[Dict]:
        """
        Make a call and parse JSON response.
        
        Args:
            system_prompt: System prompt for this call
            user_prompt: User prompt for this call
            temperature: Temperature setting
            max_tokens: Maximum tokens
            include_history: Whether to include conversation history
            
        Returns:
            Parsed JSON object or None if parsing fails
        """
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
        """Get the number of LLM calls made."""
        return self.call_count
    
    def get_history(self) -> List[Dict[str, str]]:
        """Get conversation history."""
        return self.conversation_history.copy()

