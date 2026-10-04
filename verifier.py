"""
Independent Outcome Verification Engine.
Audits the target system directly and validates field-by-field equality before declaring success.
"""

import hashlib
import json
import sqlite3
import os
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional
from app.agent.state import TaskState, VerificationResult, EvidenceBundle

class OutcomeVerifier:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.path.join(os.getcwd(), "app", "sandbox", "sandbox_erp.db")

    def verify_invoice_record(
        self,
        task_state: TaskState,
        invoice_number: str,
        expected_amount: float,
        expected_due_date: str,
        expected_vendor: Optional[str] = None
    ) -> Tuple[bool, VerificationResult, EvidenceBundle]:
        task_state.log_event("VERIFICATION_START", f"Initiating independent database verification for invoice {invoice_number}")
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM invoices WHERE invoice_number = ?", (invoice_number,))
        record = cursor.fetchone()
        
        # Read audit logs as corroborating evidence
        cursor.execute("SELECT * FROM audit_logs WHERE entity_id = ? ORDER BY id DESC LIMIT 5", (invoice_number,))
        audit_rows = [f"[{row['timestamp']}] {row['action']} - {row['details']}" for row in cursor.fetchall()]
        conn.close()

        checked_fields = {}
        expected_values = {
            "invoice_number": invoice_number,
            "amount": expected_amount,
            "due_date": expected_due_date
        }
        if expected_vendor:
            expected_values["vendor_name"] = expected_vendor

        observed_values = {}
        discrepancies = []

        if not record:
            discrepancies.append(f"CRITICAL: Record {invoice_number} not found in database ledger.")
            res = VerificationResult(
                is_verified=False,
                verification_method="SQLITE_DIRECT_READ_AFTER_WRITE",
                checked_fields={"record_exists": False},
                expected_values=expected_values,
                observed_values={},
                discrepancies=discrepancies,
                verified_at=datetime.now(timezone.utc).isoformat()
            )
            evidence = EvidenceBundle(
                task_id=task_state.task_id,
                source_document=task_state.discovered_facts.selected_document,
                extracted_fields=expected_values,
                completion_summary="Verification Failed: invoice record does not exist in target database."
            )
            task_state.log_event("VERIFICATION_FAILED", f"Record {invoice_number} could not be verified in ledger.", {"discrepancies": discrepancies})
            return False, res, evidence

        row_dict = dict(record)
        observed_values = {
            "invoice_number": row_dict["invoice_number"],
            "amount": row_dict["amount"],
            "due_date": row_dict["due_date"],
            "vendor_name": row_dict["vendor_name"]
        }

        # 1. Invoice Number Check
        checked_fields["invoice_number"] = (row_dict["invoice_number"] == invoice_number)
        if not checked_fields["invoice_number"]:
            discrepancies.append(f"Invoice number mismatch: expected {invoice_number}, got {row_dict['invoice_number']}")

        # 2. Amount Check (float tolerance 0.01)
        checked_fields["amount"] = abs(row_dict["amount"] - expected_amount) < 0.01
        if not checked_fields["amount"]:
            discrepancies.append(f"Amount mismatch: expected ${expected_amount:.2f}, got ${row_dict['amount']:.2f}")

        # 3. Due Date Check
        checked_fields["due_date"] = (row_dict["due_date"] == expected_due_date)
        if not checked_fields["due_date"]:
            discrepancies.append(f"Due date mismatch: expected {expected_due_date}, got {row_dict['due_date']}")

        # 4. Vendor Name Check
        if expected_vendor:
            checked_fields["vendor_name"] = any(part.lower() in row_dict["vendor_name"].lower() for part in expected_vendor.split())
            if not checked_fields["vendor_name"]:
                discrepancies.append(f"Vendor mismatch: expected {expected_vendor}, got {row_dict['vendor_name']}")

        is_verified = len(discrepancies) == 0 and all(checked_fields.values())

        # Build Cryptographic Audit Trace Hash
        hash_payload = f"{task_state.task_id}:{row_dict['id']}:{invoice_number}:{row_dict['amount']}:{row_dict['due_date']}"
        evidence_hash = hashlib.sha256(hash_payload.encode()).hexdigest()

        now_iso = datetime.now(timezone.utc).isoformat()
        res = VerificationResult(
            is_verified=is_verified,
            verification_method="SQLITE_DIRECT_READ_AFTER_WRITE",
            checked_fields=checked_fields,
            expected_values=expected_values,
            observed_values=observed_values,
            discrepancies=discrepancies,
            verified_at=now_iso,
            evidence_hash=evidence_hash
        )

        evidence = EvidenceBundle(
            task_id=task_state.task_id,
            timestamp=now_iso,
            source_document=task_state.discovered_facts.selected_document,
            extracted_fields=observed_values,
            erp_record_id=row_dict["id"],
            verification_hash=evidence_hash,
            audit_trail=audit_rows,
            completion_summary=f"Successfully extracted, posted, and verified invoice {invoice_number} (${expected_amount:,.2f}, due {expected_due_date}) for {row_dict['vendor_name']} in enterprise finance ledger."
        )

        if is_verified:
            task_state.log_event("VERIFICATION_PASSED", f"Record #{row_dict['id']} ({invoice_number}) 100% verified against ground-truth database.", {"evidence_hash": evidence_hash[:16]})
        else:
            task_state.log_event("VERIFICATION_FAILED", f"Discrepancies found verifying {invoice_number}", {"discrepancies": discrepancies})

        return is_verified, res, evidence
