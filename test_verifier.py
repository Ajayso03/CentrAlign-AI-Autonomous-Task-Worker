import pytest
from app.agent.verifier import OutcomeVerifier
from app.agent.state import TaskState
from app.sandbox.erp_server import reset_database, get_db

def test_verifier_detects_existing_record():
    reset_database()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO invoices (invoice_number, vendor_name, amount, currency, due_date, status, created_at, created_by)
        VALUES ('TEST-INV-1', 'Acme Industrial Hardware & Cloud Services Inc.', 2500.0, 'USD', '2026-10-01', 'RECORDED', '2026-10-01T00:00:00Z', 'TEST')
    ''')
    conn.commit()
    conn.close()

    verifier = OutcomeVerifier()
    state = TaskState(original_prompt="test")
    is_ver, res, evidence = verifier.verify_invoice_record(
        task_state=state,
        invoice_number="TEST-INV-1",
        expected_amount=2500.0,
        expected_due_date="2026-10-01",
        expected_vendor="Acme"
    )
    assert is_ver is True
    assert res.is_verified is True
    assert len(res.discrepancies) == 0
    assert len(res.evidence_hash) == 64

def test_verifier_detects_missing_record():
    reset_database()
    verifier = OutcomeVerifier()
    state = TaskState(original_prompt="test")
    is_ver, res, evidence = verifier.verify_invoice_record(
        task_state=state,
        invoice_number="NONEXISTENT-999",
        expected_amount=100.0,
        expected_due_date="2026-10-01"
    )
    assert is_ver is False
    assert len(res.discrepancies) > 0
