"""
Base Tool Abstraction for CentrAlign Agent System.
"""

import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from app.agent.state import RiskLevel, ToolCallRecord

class BaseTool(ABC):
    def __init__(self, name: str, description: str, risk_level: RiskLevel = RiskLevel.LOW):
        self.name = name
        self.description = description
        self.risk_level = risk_level

    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """Executes the tool with given arguments and returns a dictionary result."""
        pass

    def run_with_telemetry(self, **kwargs) -> ToolCallRecord:
        start_time = time.perf_counter()
        try:
            result = self.execute(**kwargs)
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return ToolCallRecord(
                tool_name=self.name,
                input_arguments=kwargs,
                output_result=result,
                status="SUCCESS",
                duration_ms=round(duration_ms, 2),
                risk_level=self.risk_level
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return ToolCallRecord(
                tool_name=self.name,
                input_arguments=kwargs,
                output_result=None,
                status="ERROR",
                error_detail=str(e),
                duration_ms=round(duration_ms, 2),
                risk_level=self.risk_level
            )
