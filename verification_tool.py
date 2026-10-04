"""
Direct Database Ground Truth Verification Tool.
"""

from typing import Dict, Any, Optional
from app.tools.base import BaseTool
from app.agent.state import RiskLevel
from app.agent.verifier import OutcomeVerifier

class DatabaseVerificationTool(BaseTool):
    def __init__(self, db_path: Optional[str] = None):
        super().__init__(
            name="verify_record",
            description="Audits SQLite finance database directly to verify ground truth state and match extracted fields.",
            risk_level=RiskLevel.LOW
        )
        self.verifier = OutcomeVerifier(db_path)

    def execute(self, **kwargs) -> Dict[str, Any]:
        task_state = kwargs.get("task_state")
        invoice_number = kwargs.get("invoice_number")
        expected_amount = float(kwargs.get("amount") if kwargs.get("amount") is not None else 0.0)
        expected_due_date = kwargs.get("due_date")
        expected_vendor = kwargs.get("vendor_name")

        is_verified, res, evidence = self.verifier.verify_invoice_record(
            task_state=task_state,
            invoice_number=invoice_number,
            expected_amount=expected_amount,
            expected_due_date=expected_due_date,
            expected_vendor=expected_vendor
        )

        return {
            "is_verified": is_verified,
            "evidence_hash": res.evidence_hash,
            "checked_fields": res.checked_fields,
            "discrepancies": res.discrepancies,
            "erp_record_id": evidence.erp_record_id
        }
