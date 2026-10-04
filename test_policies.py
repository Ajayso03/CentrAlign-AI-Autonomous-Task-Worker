import pytest
from app.agent.policies import PolicyEngine
from app.agent.state import RiskLevel, TaskState, ApprovalRequest
from app.agent.memory import CompanyGovernanceMemory

def test_policy_classification_low_risk():
    pe = PolicyEngine()
    assert pe.classify_tool_risk("search_documents", {}) == RiskLevel.LOW
    assert pe.classify_tool_risk("read_document", {}) == RiskLevel.LOW
    assert pe.classify_tool_risk("verify_record", {}) == RiskLevel.LOW

def test_policy_classification_medium_risk():
    pe = PolicyEngine()
    assert pe.classify_tool_risk("create_invoice_record", {"amount": 2500.0}) == RiskLevel.MEDIUM

def test_policy_classification_high_risk_threshold():
    pe = PolicyEngine()
    assert pe.classify_tool_risk("create_invoice_record", {"amount": 14800.0}) == RiskLevel.HIGH

def test_policy_blocks_unapproved_high_risk():
    pe = PolicyEngine()
    state = TaskState(original_prompt="High value prompt")
    permitted, risk, reason = pe.evaluate_action_permission("create_invoice_record", {"amount": 14800.0}, state)
    assert permitted is False
    assert risk == RiskLevel.HIGH
    assert "Human approval is required" in reason

def test_policy_allows_approved_high_risk():
    pe = PolicyEngine()
    state = TaskState(original_prompt="High value prompt")
    state.approval_request = ApprovalRequest(
        action_type="create_invoice_record",
        summary="Approved test",
        payload={},
        status="APPROVED"
    )
    permitted, risk, reason = pe.evaluate_action_permission("create_invoice_record", {"amount": 14800.0}, state)
    assert permitted is True
    assert risk == RiskLevel.HIGH
