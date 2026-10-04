import pytest
from app.agent.executor import TaskExecutionWorker
from app.sandbox.erp_server import reset_database
from app.agent.state import TaskStatus

def test_e2e_happy_path():
    reset_database()
    worker = TaskExecutionWorker()
    state = worker.start_task("Find the latest invoice from Acme under 5000, extract invoice number, amount, and due date, enter into finance, and verify.")
    assert state.status == TaskStatus.COMPLETED
    assert state.verification_result.is_verified is True
    assert state.discovered_facts.invoice_number == "INV-2026-1089"
    assert state.discovered_facts.amount == 4850.0

def test_e2e_self_healing_path():
    reset_database()
    worker = TaskExecutionWorker()
    state = worker.start_task("Find invoice 1099 from Acme, extract fields, enter into finance system, and verify.")
    assert state.status == TaskStatus.COMPLETED
    assert state.verification_result.is_verified is True
    assert state.discovered_facts.invoice_number == "INV-2026-1099"
    assert state.discovered_facts.due_date == "2026-09-25"
    assert any(s.status.value == "RECOVERED" for s in state.plan)

def test_e2e_human_approval_pause_and_resume():
    reset_database()
    worker = TaskExecutionWorker()
    state = worker.start_task("Find the latest invoice from Acme, extract invoice number, amount, and due date, enter into finance, and verify.")
    assert state.status == TaskStatus.WAITING_FOR_APPROVAL
    assert state.discovered_facts.amount == 14800.0
    
    # Resume with approval
    resumed = worker.resume_with_approval(state, approved=True, user_name="Alex Chen", notes="Approved")
    assert resumed.status == TaskStatus.COMPLETED
    assert resumed.verification_result.is_verified is True
