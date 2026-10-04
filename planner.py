"""
Dynamic Planning and Replanning Engine.
Decomposes goals into verifiable steps and adjusts plans based on real-time observations.
"""

from typing import List, Dict, Any, Optional
from app.agent.state import PlanStep, StepStatus, InterpretedGoal, TaskState

class DynamicPlanner:
    def create_initial_plan(self, goal: InterpretedGoal) -> List[PlanStep]:
        target = goal.target_company or "Target Company"
        steps = [
            PlanStep(
                step_id=1,
                name="search_documents",
                description=f"Search enterprise document store for invoices from '{target}'",
                tool_name="search_documents",
                tool_args={"query": target.split()[0], "doc_type": "invoices"},
                expected_output="List of matching invoice documents with metadata"
            ),
            PlanStep(
                step_id=2,
                name="inspect_and_select_latest",
                description=f"Inspect documents to extract dates and select strictly the latest invoice for '{target}'",
                tool_name="read_document",
                tool_args={},
                expected_output="Structured invoice data: invoice number, amount, date, and due date"
            ),
            PlanStep(
                step_id=3,
                name="policy_and_record_creation",
                description="Evaluate enterprise financial governance policies and submit invoice to finance ERP",
                tool_name="create_invoice_record",
                tool_args={},
                expected_output="Created invoice record in ERP ledger"
            ),
            PlanStep(
                step_id=4,
                name="inspect_web_portal",
                description="Inspect ERP web portal interface to confirm visual presentation of record",
                tool_name="inspect_web_portal",
                tool_args={},
                expected_output="Confirmation of invoice visibility in browser portal"
            ),
            PlanStep(
                step_id=5,
                name="verify_ground_truth",
                description="Perform independent read-after-write audit against ERP database to verify all fields",
                tool_name="verify_record",
                tool_args={},
                expected_output="Cryptographic verification confirmation and evidence hash"
            )
        ]
        return steps

    def replan_on_error(
        self,
        task_state: TaskState,
        failed_step: PlanStep,
        repair_action: str,
        repaired_args: Dict[str, Any]
    ) -> List[PlanStep]:
        """Dynamically modifies the execution plan upon observing a recoverable failure."""
        task_state.log_event("REPLANNING", f"Modifying plan for step {failed_step.step_id} after {repair_action}")
        
        # Update failed step to retry with repaired args
        failed_step.tool_args = repaired_args
        failed_step.status = StepStatus.IN_PROGRESS
        failed_step.retry_count += 1
        failed_step.description += f" [Auto-repaired: {repair_action}]"
        
        return task_state.plan
