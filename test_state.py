import pytest
from app.agent.state import TaskState, TaskStatus, StepStatus, PlanStep, RiskLevel

def test_task_state_initialization():
    state = TaskState(original_prompt="Test task")
    assert state.status == TaskStatus.PENDING
    assert state.current_step_index == 0
    assert len(state.execution_logs) == 0

def test_state_transitions():
    state = TaskState(original_prompt="Test task")
    state.transition(TaskStatus.INTERPRETING, "Beginning interpretation")
    assert state.status == TaskStatus.INTERPRETING
    assert len(state.execution_logs) == 1
    assert state.execution_logs[0]["event_type"] == "STATE_TRANSITION"

def test_log_event():
    state = TaskState(original_prompt="Test task")
    state.log_event("CUSTOM_EVENT", "Detailed message", {"key": "val"})
    assert len(state.execution_logs) == 1
    assert state.execution_logs[0]["details"]["key"] == "val"
