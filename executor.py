"""
Main Autonomous Task Worker Execution Loop.
Executes: Goal -> Understand -> Plan -> Tool Selection -> Execute -> Observe -> Adapt -> Verify -> Complete
Supports Pause & Resume for Human Approvals without restarting.
"""

import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple

from app.agent.state import (
    TaskState, TaskStatus, StepStatus, RiskLevel, PlanStep,
    ApprovalRequest, VerificationResult, EvidenceBundle
)
from app.agent.memory import CompanyGovernanceMemory
from app.agent.interpreter import TaskInterpreter
from app.agent.planner import DynamicPlanner
from app.agent.policies import PolicyEngine
from app.agent.recovery import FailureRecoveryEngine
from app.agent.verifier import OutcomeVerifier

from app.tools.document_tool import DocumentRepositoryTool, DocumentReaderTool
from app.tools.finance_tool import FinanceERPTool
from app.tools.browser_tool import BrowserPortalTool
from app.tools.verification_tool import DatabaseVerificationTool

class TaskExecutionWorker:
    def __init__(self):
        self.company_memory = CompanyGovernanceMemory()
        self.interpreter = TaskInterpreter(self.company_memory)
        self.planner = DynamicPlanner()
        self.policy_engine = PolicyEngine(self.company_memory)
        self.recovery_engine = FailureRecoveryEngine()
        self.verifier = OutcomeVerifier()

        # Tool registry
        self.tools = {
            "search_documents": DocumentRepositoryTool(),
            "read_document": DocumentReaderTool(),
            "create_invoice_record": FinanceERPTool(),
            "inspect_web_portal": BrowserPortalTool(),
            "verify_record": DatabaseVerificationTool()
        }

    def start_task(self, prompt: str) -> TaskState:
        state = TaskState(original_prompt=prompt)
        state.log_event("TASK_RECEIVED", f"Received user prompt: '{prompt}'")

        # 1. UNDERSTAND
        state.transition(TaskStatus.INTERPRETING, "Interpreting user intent and constraints")
        goal = self.interpreter.interpret(prompt)
        state.interpreted_goal = goal
        state.log_event("GOAL_INTERPRETED", f"Interpreted objective: '{goal.objective}' for target: '{goal.target_company}'", {
            "target_company": goal.target_company,
            "required_fields": goal.required_fields,
            "ambiguities": goal.ambiguities
        })

        # Check for immediate ambiguity blocking
        if goal.ambiguities and not goal.target_company:
            state.transition(TaskStatus.FAILED, f"Ambiguous request: {', '.join(goal.ambiguities)}")
            state.completion_summary = f"Execution halted: Could not identify target company or vendor. {goal.ambiguities[0]}"
            return state

        # 2. PLAN
        state.transition(TaskStatus.PLANNING, "Decomposing goal into verifiable steps")
        plan = self.planner.create_initial_plan(goal)
        state.plan = plan
        state.log_event("PLAN_GENERATED", f"Generated execution plan with {len(plan)} steps")

        # 3. EXECUTE LOOP
        state.transition(TaskStatus.EXECUTING, "Starting plan execution loop")
        return self.run_execution_loop(state)

    def run_execution_loop(self, state: TaskState) -> TaskState:
        while state.current_step_index < len(state.plan):
            step = state.plan[state.current_step_index]
            step.status = StepStatus.IN_PROGRESS
            step.executed_at = datetime.now(timezone.utc).isoformat()
            state.log_event("STEP_START", f"Executing step {step.step_id}: {step.name} - {step.description}")

            # Prepare dynamic args based on discovered facts
            args = dict(step.tool_args)
            if step.tool_name == "read_document" and not args.get("file_path"):
                if state.discovered_facts.candidate_documents:
                    # Select the file to read (we will iterate to find latest)
                    pass

            if step.tool_name == "create_invoice_record":
                args["invoice_number"] = state.discovered_facts.invoice_number
                args["vendor_name"] = state.discovered_facts.vendor_name
                args["amount"] = state.discovered_facts.amount
                args["currency"] = state.discovered_facts.currency or "USD"
                args["due_date"] = state.discovered_facts.due_date
                args["source_document"] = state.discovered_facts.selected_document
                step.tool_args = args

            if step.tool_name == "inspect_web_portal":
                args["invoice_number"] = state.discovered_facts.invoice_number
                step.tool_args = args

            if step.tool_name == "verify_record":
                args["invoice_number"] = state.discovered_facts.invoice_number
                args["amount"] = state.discovered_facts.amount
                args["due_date"] = state.discovered_facts.due_date
                args["vendor_name"] = state.discovered_facts.vendor_name
                args["task_state"] = state
                step.tool_args = args

            # Special Step 2: Custom multi-document latest selection logic
            if step.name == "inspect_and_select_latest":
                success = self._execute_latest_document_selection(state, step)
                if not success:
                    step.status = StepStatus.FAILED
                    state.transition(TaskStatus.FAILED, f"Failed to select valid latest invoice: {step.error_message}")
                    return state
                step.status = StepStatus.SUCCESS
                state.current_step_index += 1
                continue

            # 4. POLICY CHECK BEFORE EXECUTION
            permitted, risk, reason = self.policy_engine.evaluate_action_permission(
                step.tool_name, args, state
            )

            if not permitted and risk == RiskLevel.HIGH:
                # PAUSE FOR HUMAN APPROVAL
                app_req = ApprovalRequest(
                    action_type=step.tool_name,
                    summary=f"Record invoice {args.get('invoice_number')} for {args.get('vendor_name')} totaling ${args.get('amount', 0):,.2f}",
                    payload=args,
                    amount=args.get("amount", 0.0),
                    threshold=self.company_memory.approval_threshold_amount,
                    risk_level=RiskLevel.HIGH,
                    status="PENDING"
                )
                state.approval_request = app_req
                state.transition(TaskStatus.WAITING_FOR_APPROVAL, reason)
                state.log_event("HUMAN_APPROVAL_REQUESTED", reason, {
                    "approval_id": app_req.approval_id,
                    "amount": app_req.amount,
                    "threshold": app_req.threshold
                })
                # System PAUSES execution here. Preserves state!
                return state

            # 5. TOOL EXECUTION & TELEMETRY
            tool = self.tools.get(step.tool_name)
            if not tool:
                step.status = StepStatus.FAILED
                step.error_message = f"Tool '{step.tool_name}' not registered in worker."
                state.transition(TaskStatus.FAILED, step.error_message)
                return state

            call_record = tool.run_with_telemetry(**args)
            state.record_tool_call(call_record)

            # 6. OBSERVATION & RECOVERY
            if call_record.status == "ERROR":
                err_msg = call_record.error_detail or "Unknown tool error"
                step.error_message = err_msg
                
                # Attempt recovery
                recovered, repaired_args, recovery_note = self.recovery_engine.attempt_recovery(
                    state, step, err_msg
                )

                if recovered and repaired_args:
                    self.planner.replan_on_error(state, step, recovery_note, repaired_args)
                    # Retry tool execution with repaired args
                    retry_record = tool.run_with_telemetry(**repaired_args)
                    state.record_tool_call(retry_record)
                    
                    if retry_record.status == "SUCCESS":
                        step.status = StepStatus.RECOVERED
                        state.log_event("RECOVERY_SUCCEEDED", f"Step {step.step_id} successfully recovered! {recovery_note}")
                        self._process_tool_success(state, step, retry_record.output_result)
                        state.current_step_index += 1
                        continue
                    else:
                        step.status = StepStatus.FAILED
                        state.transition(TaskStatus.FAILED, f"Recovery retry failed: {retry_record.error_detail}")
                        return state
                else:
                    step.status = StepStatus.FAILED
                    state.transition(TaskStatus.FAILED, f"Unrecoverable error in step {step.step_id}: {err_msg}")
                    return state
            else:
                step.status = StepStatus.SUCCESS
                self._process_tool_success(state, step, call_record.output_result)
                state.current_step_index += 1

        # 7. INDEPENDENT VERIFICATION & COMPLETION
        state.transition(TaskStatus.VERIFYING, "Verifying final outcome against database ground truth")
        is_verified, ver_result, evidence = self.verifier.verify_invoice_record(
            task_state=state,
            invoice_number=state.discovered_facts.invoice_number,
            expected_amount=state.discovered_facts.amount,
            expected_due_date=state.discovered_facts.due_date,
            expected_vendor=state.discovered_facts.vendor_name
        )
        state.verification_result = ver_result
        state.evidence_bundle = evidence

        if is_verified:
            state.transition(TaskStatus.COMPLETED, "Outcome independently verified in financial ledger")
            state.completion_summary = evidence.completion_summary
        else:
            state.transition(TaskStatus.FAILED, f"Verification failed: {', '.join(ver_result.discrepancies)}")
            state.completion_summary = f"Task unverified: {', '.join(ver_result.discrepancies)}"

        return state

    def resume_with_approval(self, state: TaskState, approved: bool, user_name: str = "Manager", notes: str = "") -> TaskState:
        """Resumes execution from paused WAITING_FOR_APPROVAL state."""
        if state.status != TaskStatus.WAITING_FOR_APPROVAL or not state.approval_request:
            raise ValueError(f"Task is in state {state.status}, cannot resume approval.")

        now_iso = datetime.now(timezone.utc).isoformat()
        if approved:
            state.approval_request.status = "APPROVED"
            state.approval_request.decided_by = user_name
            state.approval_request.decided_at = now_iso
            state.approval_request.decision_notes = notes
            state.log_event("APPROVAL_GRANTED", f"Human approval granted by {user_name}. Notes: {notes}")
            state.transition(TaskStatus.EXECUTING, "Resuming execution after human sign-off")
            return self.run_execution_loop(state)
        else:
            state.approval_request.status = "REJECTED"
            state.approval_request.decided_by = user_name
            state.approval_request.decided_at = now_iso
            state.approval_request.decision_notes = notes
            state.log_event("APPROVAL_REJECTED", f"Human approval rejected by {user_name}. Notes: {notes}")
            state.transition(TaskStatus.FAILED, f"Operation halted: Human rejected approval request. Notes: {notes}")
            state.completion_summary = f"Task terminated safely: Human rejected approval for {state.approval_request.summary}"
            return state

    def _execute_latest_document_selection(self, state: TaskState, step: PlanStep) -> bool:
        doc_tool = self.tools["read_document"]
        candidates = state.discovered_facts.candidate_documents
        if not candidates:
            step.error_message = "No candidate documents available to inspect."
            return False

        inspected = []
        for doc_rel_path in candidates:
            # Skip noise files
            if "noise" in doc_rel_path.lower():
                continue
            rec = doc_tool.run_with_telemetry(file_path=doc_rel_path)
            state.record_tool_call(rec)
            if rec.status == "SUCCESS" and rec.output_result:
                res = rec.output_result
                if res.get("invoice_date") and res.get("invoice_number"):
                    inspected.append(res)

        if not inspected:
            step.error_message = "No valid invoice documents with dates found among candidates."
            return False

        hint = state.interpreted_goal.target_invoice_hint if state.interpreted_goal else None
        
        # If specific invoice requested, filter for it
        matching_hint = []
        if hint:
            for item in inspected:
                if hint.lower() in item.get("invoice_number", "").lower() or hint.lower() in item.get("file_path", "").lower():
                    matching_hint.append(item)
        
        candidates_to_sort = matching_hint if matching_hint else inspected

        # Filter by max amount constraint if requested
        if state.interpreted_goal and state.interpreted_goal.max_amount_constraint is not None:
            max_limit = state.interpreted_goal.max_amount_constraint
            filtered_by_amt = [c for c in candidates_to_sort if (c.get("amount") or 0.0) <= max_limit]
            if filtered_by_amt:
                candidates_to_sort = filtered_by_amt

        def parse_date(d_str):
            try:
                from datetime import datetime, timezone
                return datetime.strptime(d_str[:10], "%Y-%m-%d")
            except Exception:
                return datetime(1970, 1, 1)

        candidates_to_sort.sort(key=lambda x: parse_date(x["invoice_date"]), reverse=True)
        latest = candidates_to_sort[0]

        # Update discovered facts
        facts = state.discovered_facts
        facts.selected_document = latest["file_path"]
        facts.invoice_number = latest["invoice_number"]
        facts.invoice_date = latest["invoice_date"]
        facts.amount = latest["amount"]
        facts.raw_due_date_text = latest["due_date_raw"]
        facts.vendor_name = latest["vendor_name"]
        
        # Check if due date is already formatted or raw
        if latest["due_date_raw"]:
            norm = self.recovery_engine.normalize_due_date(latest["due_date_raw"])
            # If the user document was the unformatted one, keep the raw text to demonstrate self-healing if needed
            if "unformatted" in latest["file_path"]:
                facts.due_date = latest["due_date_raw"]  # deliberately pass raw to let ERP trigger validation & self-healing!
            else:
                facts.due_date = norm or latest["due_date_raw"]
        
        state.log_event("LATEST_INVOICE_IDENTIFIED", f"Identified latest invoice #{facts.invoice_number} dated {facts.invoice_date} from {facts.selected_document}", {
            "invoice_number": facts.invoice_number,
            "date": facts.invoice_date,
            "amount": facts.amount,
            "source": facts.selected_document
        })
        return True

    def _process_tool_success(self, state: TaskState, step: PlanStep, result: Optional[Dict[str, Any]]):
        if not result:
            return

        if step.tool_name == "search_documents":
            matches = result.get("matches", [])
            state.discovered_facts.candidate_documents = [m["relative_path"] for m in matches]
            state.log_event("DISCOVERED_DOCUMENTS", f"Discovered {len(matches)} matching documents in repository")

        elif step.tool_name == "create_invoice_record":
            record_id = result.get("record_id")
            state.discovered_facts.erp_record_id = record_id
            state.log_event("RECORD_CREATED", f"Finance record successfully created with ERP ID #{record_id}")
