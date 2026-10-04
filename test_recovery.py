import pytest
from app.agent.recovery import FailureRecoveryEngine
from app.agent.state import ErrorClassification, TaskState, PlanStep, StepStatus

def test_normalize_due_date_formats():
    rec = FailureRecoveryEngine()
    assert rec.normalize_due_date("2026-09-25") == "2026-09-25"
    assert rec.normalize_due_date("September 25, 2026") == "2026-09-25"
    assert rec.normalize_due_date("Sep 25, 2026") == "2026-09-25"
    assert rec.normalize_due_date("09/25/2026") == "2026-09-25"
    assert rec.normalize_due_date("August 20, 2026") == "2026-08-20"

def test_error_classification():
    rec = FailureRecoveryEngine()
    assert rec.classify_error("create_invoice_record", "HTTP 422 Validation error: due_date invalid") == ErrorClassification.RECOVERABLE_VALIDATION_ERROR
    assert rec.classify_error("create_invoice_record", "503 Service Unavailable: transient lock") == ErrorClassification.TRANSIENT_SYSTEM_ERROR
    assert rec.classify_error("search_documents", "404 File not found") == ErrorClassification.MISSING_INFORMATION

def test_attempt_recovery_date_healing():
    rec = FailureRecoveryEngine()
    state = TaskState(original_prompt="test")
    state.discovered_facts.raw_due_date_text = "September 25, 2026"
    step = PlanStep(
        step_id=3,
        name="create_record",
        description="create",
        tool_name="create_invoice_record",
        tool_args={"due_date": "September 25, 2026", "amount": 1000.0},
        expected_output="done"
    )
    recovered, repaired, note = rec.attempt_recovery(state, step, "HTTP 422 due_date invalid")
    assert recovered is True
    assert repaired["due_date"] == "2026-09-25"
