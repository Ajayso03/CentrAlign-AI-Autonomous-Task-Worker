import pytest
from app.agent.interpreter import TaskInterpreter
from app.agent.memory import CompanyGovernanceMemory

def test_interpret_known_vendor():
    interp = TaskInterpreter()
    goal = interp.interpret("Find the latest invoice from Acme and record it into finance.")
    assert goal.target_company == "Acme Industrial Hardware & Cloud Services Inc."
    assert "invoice_number" in goal.required_fields
    assert len(goal.ambiguities) == 0

def test_interpret_unknown_vendor():
    interp = TaskInterpreter()
    goal = interp.interpret("Record invoice for Stark Industries")
    assert len(goal.ambiguities) > 0

def test_interpret_amount_constraint():
    interp = TaskInterpreter()
    goal = interp.interpret("Find latest invoice from Acme under 5000")
    assert goal.max_amount_constraint == 5000.0
