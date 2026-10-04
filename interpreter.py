"""
Task Interpreter: Converts unstructured user request into structured goal specification.
"""

import re
from typing import Tuple, List, Optional
from app.agent.state import InterpretedGoal, RiskLevel
from app.agent.memory import CompanyGovernanceMemory

class TaskInterpreter:
    def __init__(self, company_memory: Optional[CompanyGovernanceMemory] = None):
        self.company_memory = company_memory or CompanyGovernanceMemory()

    def interpret(self, user_prompt: str) -> InterpretedGoal:
        p_lower = user_prompt.lower()

        # 1. Identify Target Entity / Company
        target_company = None
        ambiguities = []
        if "acme" in p_lower:
            target_company = "Acme Industrial Hardware & Cloud Services Inc."
        elif "globex" in p_lower:
            target_company = "Globex Corporation"
        elif "initech" in p_lower:
            target_company = "Initech Consulting LLC"
        else:
            # Check if user mentioned another entity or omitted it
            company_match = re.search(r"company\s+([a-zA-Z0-9_\-]+)", user_prompt, re.I)
            if company_match:
                candidate = company_match.group(1)
                matched = self.company_memory.matches_vendor(candidate)
                if matched:
                    target_company = matched
                else:
                    target_company = candidate
                    ambiguities.append(f"Target company '{candidate}' is not recognized in approved corporate vendor ledger.")
            else:
                ambiguities.append("No specific vendor or company specified in request.")

        # 2. Identify required fields
        required_fields = ["invoice_number", "amount", "due_date"]
        if "itemized" in p_lower:
            required_fields.append("itemized_charges")

        # 3. Identify Target Action & System
        target_system = "CentrAlign Enterprise ERP Ledger"
        objective = "Extract and record latest invoice into finance system"

        # 4. Assess Initial Risk Level
        risk_level = RiskLevel.MEDIUM  # Default for financial data entry
        requires_approval = False

        # If high amounts explicitly stated
        amount_match = re.search(r"\$?([0-9,]+(?:\.[0-9]{2})?)", user_prompt)
        if amount_match:
            try:
                amt = float(amount_match.group(1).replace(",", ""))
                if amt >= self.company_memory.approval_threshold_amount:
                    risk_level = RiskLevel.HIGH
                    requires_approval = True
            except ValueError:
                pass

        constraints = [
            "Must select strictly the latest invoice by invoice date",
            "Due date must be recorded strictly in ISO 8601 YYYY-MM-DD format",
            "Must verify saved record in finance database before claiming completion"
        ]

        # Check for specific invoice hint
        inv_hint_match = re.search(r"(?:invoice|inv)[\s#\-]*([0-9]{3,4}|[A-Za-z0-9\-]+)", user_prompt, re.I)
        target_invoice_hint = None
        if inv_hint_match:
            val = inv_hint_match.group(1).strip()
            if val.lower() not in ["from", "latest", "the", "system"]:
                target_invoice_hint = val

        # Check for max amount constraint (e.g. under 5000 or below 5000)
        max_amount_constraint = None
        under_match = re.search(r"(?:under|below|less\s+than)\s*\$?([0-9,]+)", user_prompt, re.I)
        if under_match:
            try:
                max_amount_constraint = float(under_match.group(1).replace(",", ""))
            except ValueError:
                pass

        return InterpretedGoal(
            objective=objective,
            target_company=target_company,
            target_invoice_hint=target_invoice_hint,
            max_amount_constraint=max_amount_constraint,
            required_fields=required_fields,
            target_system=target_system,
            risk_level=risk_level,
            requires_approval=requires_approval,
            constraints=constraints,
            ambiguities=ambiguities
        )
