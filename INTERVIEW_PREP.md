# Technical Interview Preparation Guide

This document prepares the engineer for an in-depth technical discussion with the CentrAlign AI hiring team, covering architecture, design trade-offs, failure debugging, and scalability.

---

## 1. Core Architectural Questions & Rationales

### Why this architecture?
We decoupled the system into a **modular state machine runtime** where the LLM is treated as an autonomous reasoning component, but the **surrounding software enforces state persistence, policy boundaries, tool schemas, retries, and verification**. Leaving safety and state transitions to an unstructured prompt is fragile and non-deterministic. By structuring the loop as:
$$\text{Understand} \rightarrow \text{Plan} \rightarrow \text{Policy Check} \rightarrow \text{Execute} \rightarrow \text{Observe} \rightarrow \text{Self-Heal} \rightarrow \text{Verify} \rightarrow \text{Complete}$$
the system guarantees that every action is observable, bounded, and verifiable.

### Why this model strategy?
We implemented a **hybrid autonomous architecture**:
1. A **deterministic rule-and-heuristic reasoning engine** that runs 100% locally out of the box with zero external dependencies or API keys. This guarantees immediate reproducibility for any hiring engineer evaluating the repo.
2. An extensible provider layer (`app/agent/llm_provider.py`) that can seamlessly route queries to Claude 3.5 Sonnet, GPT-4o, or Gemini 1.5 Pro if API keys are provided in `.env`.

### Why this agent framework?
We built a custom, lightweight framework using pure Python, Pydantic, and FastAPI rather than bulky frameworks like LangChain or CrewAI. Custom runtimes eliminate unnecessary abstraction layers, make every state transition visible in code, run in milliseconds, and ensure the candidate understands every line of execution logic.

### How does planning work?
The `DynamicPlanner` (`app/agent/planner.py`) decomposes natural language objectives into discrete `PlanStep` objects with explicit tool names, input arguments, and expected outputs. When an observation contradicts the plan (e.g. an HTTP 422 validation failure), `replan_on_error()` updates the step arguments in-place, increments retries, and dynamically modifies execution without losing accumulated state.

### How does the agent decide which tool to use?
Tools are mapped during plan generation based on entity and task classification:
- Document discovery $\rightarrow$ `search_documents`
- Document extraction $\rightarrow$ `read_document`
- Financial ledger posting $\rightarrow$ `create_invoice_record`
- UI validation $\rightarrow$ `inspect_web_portal`
- Ground-truth confirmation $\rightarrow$ `verify_record`

### How do you prevent infinite loops?
1. Every `PlanStep` has a strict `max_retries` counter (default: 3).
2. The `FailureRecoveryEngine` only attempts self-healing if a concrete repair strategy is available (e.g., date normalization). If no recovery strategy matches, it marks the error as `FATAL_ERROR` and halts.
3. Total plan step index strictly increments on success or recovery.

### How do you detect failures?
Failures are captured in the observation loop:
- `ToolCallRecord.status == "ERROR"`
- HTTP response codes (422 Unprocessable Entity, 503 Service Unavailable, 404 Not Found)
- The `FailureRecoveryEngine.classify_error()` categorizes errors into `RECOVERABLE_VALIDATION_ERROR`, `TRANSIENT_SYSTEM_ERROR`, `MISSING_INFORMATION`, or `POLICY_VIOLATION`.

### How do retries work?
- For `TRANSIENT_SYSTEM_ERROR`: Exponential backoff with jitter ($2^{\text{retry}} \times 0.1\text{s}$).
- For `RECOVERABLE_VALIDATION_ERROR`: Input repair (e.g. normalizing `"September 25, 2026"` to `"2026-09-25"`), followed by an immediate targeted retry.
- For non-recoverable errors: Safe termination without wasteful retries.

### How do you know the task actually succeeded?
We separate execution from verification. A tool returning `201 Created` is merely an assertion, not a proof. The `OutcomeVerifier` runs an independent read-after-write database audit against SQLite, checks every field (`invoice_number`, `amount`, `due_date`, `vendor`), and generates a SHA-256 cryptographic evidence hash.

### Why is verification separate from execution?
Because distributed systems experience silent drops, queue drops, and schema truncations. An agent that considers an API call's return code as proof of completion is unsafe for enterprise finance.

### How does memory work?
Memory is strictly partitioned into:
1. `TaskExecutionMemory`: Ephemeral facts discovered during active execution.
2. `CompanyGovernanceMemory`: Long-term enterprise rules (vendors, AP-04 threshold $5,000, date standards).

### How would this scale?
- Replace SQLite with PostgreSQL / Redis with row-level encryption.
- Wrap the execution loop in Temporal or Cadence workflows for multi-day durable execution.
- Distribute worker execution across Celery / Kubernetes pods.

### What happens if the browser changes?
For browser automation, we maintain semantic locator fallbacks (e.g., text-based matching, ARIA roles, and LLM visual grounding via Playwright) rather than brittle CSS selectors.

### What happens if the model hallucinates?
The surrounding code enforces strict validation:
- Tool arguments are validated against Pydantic schemas.
- Target vendors must match the approved vendor ledger.
- Final verification checks database ground truth.

### How would you handle conflicting instructions?
The `TaskInterpreter` evaluates constraints and flags conflicts during the `INTERPRETING` phase, transitioning the task to `FAILED` with an explicit clarification request before any tools execute.

### How would you handle permissions and sensitive actions?
The `PolicyEngine` enforces risk classifications (`LOW`, `MEDIUM`, `HIGH`). Any operation $\ge$ $5,000 forces execution into `WAITING_FOR_APPROVAL` regardless of user phrasing.

## 2. 10 Likely Technical Interview Questions & Concrete Answers

### Q1: In your code, where does dynamic replanning actually take place?
**Answer:** In `app/agent/planner.py` inside `DynamicPlanner.replan_on_error()`. When `TaskExecutionWorker.run_execution_loop()` in `executor.py` catches a tool error, it invokes `recovery_engine.attempt_recovery()`. If a repair is generated, `replan_on_error()` updates the active `PlanStep`'s `tool_args`, updates the description, and restarts execution on that step without wiping previously discovered facts.

### Q2: How does your human-in-the-loop implementation avoid losing state when waiting for an approval?
**Answer:** The `TaskState` is a serialized Pydantic model. When `PolicyEngine` detects amount $\ge$ $5,000, `executor.py` sets `status = WAITING_FOR_APPROVAL` and returns the `TaskState` directly. It does not terminate or restart. When the user approves via `POST /api/agent/approve`, `worker.resume_with_approval()` sets `status = EXECUTING` and re-enters the loop at `current_step_index`, preserving all prior discoveries.

### Q3: What prevents the agent from claiming success if an API call succeeds but the database write was dropped?
**Answer:** The independent `OutcomeVerifier` in `app/agent/verifier.py`. After the plan finishes, the worker executes a separate phase (`TaskStatus.VERIFYING`) that opens an independent SQLite connection, queries `SELECT * FROM invoices WHERE invoice_number = ?`, and validates each field. If the record is missing, it sets `is_verified = False`, appends a critical discrepancy, and marks the task as `FAILED`.

### Q4: How does your system differentiate between noise files and actual invoices?
**Answer:** `DocumentReaderTool` in `app/tools/document_tool.py` inspects file content for standard invoice tokens (`Invoice Number:`, `Invoice Date:`, `Total Due:`). In `_execute_latest_document_selection()`, any candidate matching noise files (e.g. `employee_handbook.txt`) is ignored because it lacks invoice header fields.

### Q5: How do you handle transient failures versus permanent failures?
**Answer:** `FailureRecoveryEngine.classify_error()` inspects status codes and error messages. HTTP 503 errors are tagged as `TRANSIENT_SYSTEM_ERROR`, triggering exponential backoff (`2^retry * 0.1s`). HTTP 422 errors are tagged as `RECOVERABLE_VALIDATION_ERROR`, triggering input healing. Unrecognized errors are tagged as `FATAL_ERROR`, halting immediately.

### Q6: Why did you implement a deterministic engine alongside the LLM provider?
**Answer:** To guarantee that the hiring team can run tests, evaluation benchmarks, and the web console locally with 100% reproducibility in any environment without needing paid API keys or hitting rate limits.

### Q7: What telemetry data is captured for each tool call?
**Answer:** `ToolCallRecord` records: `call_id` (UUID), `tool_name`, `timestamp` (UTC ISO), `input_arguments`, `output_result`, `status` ("SUCCESS" or "ERROR"), `error_detail`, `duration_ms` (using `time.perf_counter()`), and `risk_level`.

### Q8: What cryptographic standard do you use for verification evidence?
**Answer:** SHA-256 computed over the tuple: `task_id : record_id : invoice_number : amount : due_date`. This creates an immutable audit fingerprint.

### Q9: How is the maximum spending threshold enforced?
**Answer:** In `app/agent/policies.py` via `CompanyGovernanceMemory.approval_threshold_amount = 5000.0`. The policy check happens before tool invocation in `executor.py` line 122. If unapproved, execution halts before calling the ERP API.

### Q10: How does your system select the latest invoice when multiple invoices exist?
**Answer:** `_execute_latest_document_selection()` inspects candidate invoices, parses their `invoice_date` into datetime objects, and sorts descending. If the user specifies constraints (e.g. "under 5000"), it filters out candidates exceeding the limit before sorting.

---

## 3. 5 Real Debugging Walkthroughs

### Scenario 1: Date Format Validation Error (HTTP 422)
- **Symptom:** `FinanceERPTool` throws `HTTP 422 Validation error: Field due_date 'September 25, 2026' must be in strict ISO 8601 (YYYY-MM-DD) format.`
- **Inspection:** Worker catches `ValueError`, passes error string to `FailureRecoveryEngine.classify_error()`.
- **Resolution:** Classifier tags it as `RECOVERABLE_VALIDATION_ERROR`. `normalize_due_date()` converts string to `"2026-09-25"`. Dynamic replanner updates step args and retries. Step marked `RECOVERED`.

### Scenario 2: Silent Drop in Asynchronous Pipeline
- **Symptom:** ERP API returns simulated HTTP 201 success, but database write never occurred.
- **Inspection:** `OutcomeVerifier` queries SQLite database for record; returns `None`.
- **Resolution:** Verifier registers discrepancy: `CRITICAL: Record INV-2026-1089 not found in database ledger.` Task transitions to `FAILED`.

### Scenario 3: Unauthorized High-Value Disbursement
- **Symptom:** User prompts agent to record Acme invoice #1102 ($14,800.00).
- **Inspection:** `PolicyEngine.evaluate_action_permission()` detects amount > $5,000 threshold without prior approval.
- **Resolution:** Policy blocks execution; creates `ApprovalRequest`; pauses task in `WAITING_FOR_APPROVAL` until human signs off.

### Scenario 4: Unknown / Ambiguous Vendor
- **Symptom:** User prompts: `"Find invoice from Wayne Enterprises"`.
- **Inspection:** `TaskInterpreter` checks `CompanyGovernanceMemory.is_approved_vendor("Wayne Enterprises")` $\rightarrow$ returns `False`.
- **Resolution:** Goal flagged with ambiguity: `"Target company 'Wayne Enterprises' is not recognized in approved corporate vendor ledger."` Worker halts safely.

### Scenario 5: Concurrency / Database Pool Exhaustion (HTTP 503)
- **Symptom:** Database throws transient connection lock.
- **Inspection:** Recovery engine catches 503, applies exponential backoff with sleep timer, and re-executes step successfully.

---

## 4. 5 Architecture Extension Scenarios

1. **Adding Computer-Use & Vision Grounding**:
   Replace `BrowserPortalTool` with Playwright and Claude 3.5 Computer Use. Send screenshot and accessibility tree to model; model returns coordinate-based click/type actions; system verifies DOM state change after action.

2. **Transitioning to Distributed Durable Execution**:
   Wrap `TaskExecutionWorker.run_execution_loop()` in a **Temporal Workflow**. Steps become Temporal Activities. If a worker pod crashes while waiting for human approval, another worker resumes from workflow history with zero state loss.

3. **Enterprise RAG & Multi-Tenant Document Stores**:
   Replace local filesystem search with vector search over Milvus / Pinecone with tenant partition keys. Embed corporate invoices and procurement documents using text embeddings.

4. **Multi-Level Approval Matrix**:
   Extend `PolicyEngine` with tiered escalation:
   - < $5,000: Auto-approved
   - $5,000 ? $25,000: Team Lead approval
   - > $25,000: VP of Finance approval + 2FA token verification

5. **Immutable Audit Ledger**:
   Stream `EvidenceBundle` hashes to an AWS QLDB (Quantum Ledger Database) or cryptographic append-only merkle tree for enterprise compliance (SOX, SOC 2).
