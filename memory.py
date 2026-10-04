"""
Scoped Enterprise Memory System.
Separates ephemeral task-level discoveries from persistent company-wide governance.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class CompanyGovernanceMemory(BaseModel):
    company_name: str = "CentrAlign Systems Corp"
    financial_currency: str = "USD"
    approval_threshold_amount: float = 5000.0
    date_format_requirement: str = "YYYY-MM-DD"
    approved_vendors: List[str] = Field(default_factory=lambda: [
        "Acme Industrial Hardware & Cloud Services Inc.",
        "Globex Corporation",
        "Initech Consulting LLC"
    ])
    erp_system_name: str = "CentrAlign Enterprise Finance ERP"
    ap_policy_document_ref: str = "noise/expense_policy.txt"

    def is_approved_vendor(self, vendor_query: str) -> bool:
        v_low = vendor_query.lower()
        for v in self.approved_vendors:
            if v_low in v.lower() or v.lower() in v_low:
                return True
        return False

    def matches_vendor(self, query: str) -> Optional[str]:
        q_low = query.lower()
        for v in self.approved_vendors:
            if q_low in v.lower() or any(part.lower() in v.lower() for part in q_low.split()):
                return v
        return None

class TaskExecutionMemory(BaseModel):
    facts: Dict[str, Any] = Field(default_factory=dict)
    inspected_documents: List[str] = Field(default_factory=list)
    rejection_reasons: List[str] = Field(default_factory=list)

    def remember(self, key: str, value: Any):
        self.facts[key] = value

    def recall(self, key: str, default: Any = None) -> Any:
        return self.facts.get(key, default)
