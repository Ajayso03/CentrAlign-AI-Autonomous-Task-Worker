"""
Software-Enforced Policy and Permissions Engine.
Guarantees safety boundaries, permission gates, and human approval enforcement.
"""

from typing import Tuple, Dict, Any, Optional
from app.agent.state import RiskLevel, TaskState, ApprovalRequest
from app.agent.memory import CompanyGovernanceMemory

class PolicyEngine:
    def __init__(self, company_memory: Optional[CompanyGovernanceMemory] = None):
        self.company_memory = company_memory or CompanyGovernanceMemory()

    def classify_tool_risk(self, tool_name: str, tool_args: Dict[str, Any]) -> RiskLevel:
        if tool_name in ["search_documents", "read_document", "inspect_web_portal", "list_vendors"]:
            return RiskLevel.LOW
        
        if tool_name == "create_invoice_record":
            raw_amt = tool_args.get("amount")
            amount = float(raw_amt) if raw_amt is not None else 0.0
            if amount >= self.company_memory.approval_threshold_amount:
                return RiskLevel.HIGH
            return RiskLevel.MEDIUM

        if tool_name in ["delete_record", "cancel_invoice", "modify_bank_details"]:
            return RiskLevel.HIGH

        if tool_name == "verify_record":
            return RiskLevel.LOW

        return RiskLevel.MEDIUM

    def evaluate_action_permission(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        task_state: TaskState
    ) -> Tuple[bool, RiskLevel, Optional[str]]:
        risk = self.classify_tool_risk(tool_name, tool_args)

        # LOW risk actions are unconditionally safe
        if risk == RiskLevel.LOW:
            return True, risk, None

        # MEDIUM risk actions (e.g. creating invoice under $5,000) are permitted with audit
        if risk == RiskLevel.MEDIUM:
            return True, risk, None

        # HIGH risk actions (e.g. invoice >= $5,000) require approved human sign-off
        if risk == RiskLevel.HIGH:
            app_req = task_state.approval_request
            if app_req and app_req.status == "APPROVED":
                return True, risk, None
            else:
                reason = (
                    f"Financial Policy Enforced: Action '{tool_name}' involves amount "
                    f"${tool_args.get('amount', 0):,.2f} which equals or exceeds governance "
                    f"threshold (${self.company_memory.approval_threshold_amount:,.2f}). "
                    f"Human approval is required before execution."
                )
                return False, risk, reason

        return False, risk, "Unknown policy boundary."
