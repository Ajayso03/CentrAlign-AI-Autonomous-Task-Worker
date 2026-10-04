"""
Failure Recovery, Retry Policies, and Automated Self-Healing.
"""

import re
import time
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from app.agent.state import ErrorClassification, TaskState, PlanStep, StepStatus

class FailureRecoveryEngine:
    def classify_error(self, tool_name: str, error_msg: str, status_code: Optional[int] = None) -> ErrorClassification:
        err_lower = error_msg.lower()
        if "503" in err_lower or "transient" in err_lower or "connection pool" in err_lower:
            return ErrorClassification.TRANSIENT_SYSTEM_ERROR
        if "422" in err_lower or "validation error" in err_lower or "due_date" in err_lower or "iso 8601" in err_lower:
            return ErrorClassification.RECOVERABLE_VALIDATION_ERROR
        if "404" in err_lower or "not found" in err_lower or "missing" in err_lower:
            return ErrorClassification.MISSING_INFORMATION
        if "policy" in err_lower or "threshold" in err_lower or "approval" in err_lower:
            return ErrorClassification.POLICY_VIOLATION
        if "verification" in err_lower or "mismatch" in err_lower:
            return ErrorClassification.VERIFICATION_FAILED
        return ErrorClassification.FATAL_ERROR

    def normalize_due_date(self, raw_date_str: str) -> Optional[str]:
        raw = raw_date_str.strip()
        # Already YYYY-MM-DD
        if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
            return raw

        # e.g. 09/25/2026 or 9/25/2026
        match_slash = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", raw)
        if match_slash:
            m, d, y = match_slash.groups()
            return f"{y}-{int(m):02d}-{int(d):02d}"

        # e.g. September 25, 2026 or Sep 25, 2026
        months = {
            "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
            "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
            "aug": 8, "august": 8, "sep": 9, "september": 9, "oct": 10, "october": 10,
            "nov": 11, "november": 11, "dec": 12, "december": 12
        }
        match_text = re.search(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", raw)
        if match_text:
            month_str, d, y = match_text.groups()
            m_num = months.get(month_str.lower()[:3]) or months.get(month_str.lower())
            if m_num:
                return f"{y}-{m_num:02d}-{int(d):02d}"

        return None

    def attempt_recovery(
        self,
        task_state: TaskState,
        step: PlanStep,
        error_msg: str
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        classification = self.classify_error(step.tool_name, error_msg)
        task_state.log_event("FAILURE_DETECTED", f"Error encountered in step {step.step_id}: {error_msg}", {
            "classification": classification.value,
            "tool": step.tool_name,
            "retry_count": step.retry_count
        })

        # 1. Recoverable Validation Error: Date formatting issue
        if classification == ErrorClassification.RECOVERABLE_VALIDATION_ERROR and step.tool_name == "create_invoice_record":
            current_due_date = step.tool_args.get("due_date", "")
            raw_text = task_state.discovered_facts.raw_due_date_text or current_due_date
            normalized = self.normalize_due_date(raw_text)
            if normalized and normalized != current_due_date:
                repaired_args = dict(step.tool_args)
                repaired_args["due_date"] = normalized
                task_state.discovered_facts.due_date = normalized
                task_state.log_event(
                    "AUTONOMOUS_SELF_HEALING",
                    f"Repaired due_date format from '{current_due_date}' to ISO 8601 '{normalized}'",
                    {"original": current_due_date, "repaired": normalized}
                )
                return True, repaired_args, f"Self-healed invalid date to ISO 8601 '{normalized}'"

        # 2. Transient System Error: Retry with backoff
        if classification == ErrorClassification.TRANSIENT_SYSTEM_ERROR:
            if step.retry_count < step.max_retries:
                backoff_sec = (2 ** step.retry_count) * 0.1
                task_state.log_event("RETRY_BACKOFF", f"Transient error. Backing off for {backoff_sec:.2f}s before retry {step.retry_count + 1}/{step.max_retries}")
                time.sleep(backoff_sec)
                return True, step.tool_args, f"Retrying after transient backoff (attempt {step.retry_count + 1})"

        return False, None, f"Non-recoverable failure: {classification.value} - {error_msg}"
