"""
Autonomous Reasoning & Model Provider Layer.
Provides unified reasoning:
1. Built-in Deterministic Enterprise Reasoner (zero-cost, runs out of the box with 0 external keys)
2. Optional external LLM (OpenAI / Anthropic / Gemini) if API keys are set in environment.
"""

import os
from typing import Dict, Any, Optional

class LLMProvider:
    def __init__(self):
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        
        if self.openai_key:
            self.provider_mode = "OPENAI"
            self.model_name = "gpt-4o"
        elif self.anthropic_key:
            self.provider_mode = "ANTHROPIC"
            self.model_name = "claude-3-5-sonnet"
        elif self.gemini_key:
            self.provider_mode = "GEMINI"
            self.model_name = "gemini-1.5-pro"
        else:
            self.provider_mode = "DETERMINISTIC_AUTONOMOUS_ENGINE"
            self.model_name = "centralign-rule-reasoner-v1"

    def describe(self) -> Dict[str, str]:
        return {
            "provider": self.provider_mode,
            "model": self.model_name,
            "zero_config_fallback": "Active" if self.provider_mode == "DETERMINISTIC_AUTONOMOUS_ENGINE" else "Inactive"
        }
