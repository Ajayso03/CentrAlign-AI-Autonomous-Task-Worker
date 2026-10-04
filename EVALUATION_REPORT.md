# CentrAlign AI ? Autonomous Task Worker Benchmark Report

**Generated At:** 2026-10-04T09:00:58.797694+00:00Z  
**Evaluation Harness:** `app/evaluation/harness.py`  
**System:** Autonomous AI Task Worker v1.0 (CentrAlign AI Engineering Intern Submission)

---

## 1. Executive Summary

| Metric | Measured Value | Target Standard | Status |
| :--- | :--- | :--- | :--- |
| **Task Completion & Accuracy** | **100.0%** (5/5) | > 90% | **EXCELLENT** |
| **Verification Accuracy** | **100.0%** | 100% | **PERFECT** |
| **Self-Healing & Recovery** | **100% Recoverable** (1 self-heals) | 100% | **ROBUST** |
| **Average End-to-End Latency** | **36.84 ms** | < 1,000 ms | **OPTIMAL** |
| **Mean Tool Calls / Task** | **6.6 calls** | 3?8 calls | **EFFICIENT** |

---

## 2. Detailed Scenario Breakdown

| Scenario ID | Name & Objective | Tool Calls | Retries | Verified | Result |
| :--- | :--- | :---: | :---: | :---: | :---: |
| `happy_path` | Final Status: COMPLETED (Expected: COMPLETED), Verified: True (Expected: True) | 8 | 0 | True | **? PASSED** |
| `failure_recovery` | Final Status: COMPLETED (Expected: COMPLETED), Verified: True (Expected: True), Self-Healing Triggered: True | 9 | 1 | True | **? PASSED** |
| `human_approval` | Final Status: COMPLETED (Expected: COMPLETED), Verified: True (Expected: True) | 8 | 0 | True | **? PASSED** |
| `ambiguous_input` | Final Status: FAILED (Expected: FAILED), Verified: False (Expected: False) | 0 | 0 | False | **? PASSED** |
| `verification_failure` | Final Status: FAILED (Expected: FAILED), Verified: False (Expected: False) | 8 | 0 | False | **? PASSED** |

---

## 3. Engineering Analysis of Observed Autonomy

### Scenario 1: Happy Path
- **Observation:** The agent correctly identifies Acme document candidate `acme_inv_1089_latest.txt` ($4,850.00), extracts fields, passes policy check (amount < $5,000), calls ERP tool, and independently verifies ground truth in SQLite.
- **Evidence:** Cryptographic hash generated and verified.

### Scenario 2: Autonomous Error Recovery (Self-Healing)
- **Observation:** The agent encountered an unformatted date (`September 25, 2026`) which triggered an HTTP 422 schema validation error from the ERP.
- **Autonomous Action:** The agent observed the 422 error, inspected task state, invoked `normalize_due_date()`, dynamically replanned the failed step, and executed a successful retry with ISO 8601 date `2026-09-25`.
- **Verdict:** True agentic loop (`Execute -> Observe -> Adapt -> Verify -> Complete`).

### Scenario 3: Software-Enforced Policy & Human Approval
- **Observation:** Enterprise invoice for $14,800.00 triggered Policy AP-04 threshold ($5,000.00).
- **Control:** The agent halted before state mutation, serialized task state to `WAITING_FOR_APPROVAL`, and waited for human manager authorization. Upon approval, execution resumed seamlessly without restarting.

### Scenario 4: Ambiguity & Hallucination Defense
- **Observation:** Request for non-existent company ("Wayne Enterprises").
- **Control:** The agent flagged missing vendor ambiguity during interpretation and halted safely instead of inventing fake records.

### Scenario 5: Defense Against False Positive Pipeline Drops
- **Observation:** The ERP simulated an acceptance response, but the database write was silently dropped.
- **Defense:** The independent verifier caught the missing record during read-after-write audit and marked the task as `FAILED` rather than claiming false success.
