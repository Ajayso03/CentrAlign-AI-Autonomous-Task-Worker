"""
Task State Machine & Data Models for CentrAlign Autonomous AI Task Worker.
Maintains explicit, fully-serializable, observable state throughout execution.
"""

import uuid
from enum import Enum
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class TaskStatus(str, Enum):
    PENDING = "PENDING"
    INTERPRETING = "INTERPRETING"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class StepStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS = "SUCCESS"
    RECOVERED = "RECOVERED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"

class ErrorClassification(str, Enum):
    RECOVERABLE_VALIDATION_ERROR = "RECOVERABLE_VALIDATION_ERROR"
    TRANSIENT_SYSTEM_ERROR = "TRANSIENT_SYSTEM_ERROR"
    MISSING_INFORMATION = "MISSING_INFORMATION"
    POLICY_VIOLATION = "POLICY_VIOLATION"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    FATAL_ERROR = "FATAL_ERROR"

class InterpretedGoal(BaseModel):
    objective: str = Field(..., description="High level goal of the user")
    target_company: Optional[str] = Field(None, description="Identified vendor or entity name")
    target_invoice_hint: Optional[str] = Field(None, description="Specific invoice number or keyword if requested")
    max_amount_constraint: Optional[float] = Field(None, description="Maximum amount filter if specified (e.g. under 5000)")
    required_fields: List[str] = Field(default_factory=list, description="Fields required to be extracted")
    target_system: str = Field("ERP_FINANCE", description="Target application or ledger")
    risk_level: RiskLevel = Field(RiskLevel.LOW, description="Calculated task risk classification")
    requires_approval: bool = Field(False, description="Flag if human approval is mandatory")
    constraints: List[str] = Field(default_factory=list, description="Extracted execution constraints")
    ambiguities: List[str] = Field(default_factory=list, description="Detected ambiguities or missing details")

class PlanStep(BaseModel):
    step_id: int
    name: str
    description: str
    tool_name: str
    tool_args: Dict[str, Any] = Field(default_factory=dict)
    expected_output: str
    status: StepStatus = StepStatus.NOT_STARTED
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    executed_at: Optional[str] = None

class DiscoveredFacts(BaseModel):
    vendor_name: Optional[str] = None
    candidate_documents: List[str] = Field(default_factory=list)
    selected_document: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = "USD"
    raw_due_date_text: Optional[str] = None
    erp_record_id: Optional[int] = None
    extra_metadata: Dict[str, Any] = Field(default_factory=dict)

class ToolCallRecord(BaseModel):
    call_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    tool_name: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    input_arguments: Dict[str, Any]
    output_result: Optional[Dict[str, Any]] = None
    status: str = "SUCCESS"  # SUCCESS or ERROR
    error_detail: Optional[str] = None
    duration_ms: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW

class ApprovalRequest(BaseModel):
    approval_id: str = Field(default_factory=lambda: f"APP-{str(uuid.uuid4())[:6].upper()}")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    action_type: str
    summary: str
    payload: Dict[str, Any]
    amount: Optional[float] = None
    threshold: float = 5000.0
    risk_level: RiskLevel = RiskLevel.HIGH
    status: str = "PENDING"  # PENDING, APPROVED, REJECTED
    decided_by: Optional[str] = None
    decided_at: Optional[str] = None
    decision_notes: Optional[str] = None

class VerificationResult(BaseModel):
    is_verified: bool = False
    verification_method: str = "INDEPENDENT_DB_QUERY"
    checked_fields: Dict[str, bool] = Field(default_factory=dict)
    expected_values: Dict[str, Any] = Field(default_factory=dict)
    observed_values: Dict[str, Any] = Field(default_factory=dict)
    discrepancies: List[str] = Field(default_factory=list)
    verified_at: Optional[str] = None
    evidence_hash: Optional[str] = None

class EvidenceBundle(BaseModel):
    task_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source_document: Optional[str] = None
    extracted_fields: Dict[str, Any] = Field(default_factory=dict)
    erp_record_id: Optional[int] = None
    verification_hash: Optional[str] = None
    audit_trail: List[str] = Field(default_factory=list)
    completion_summary: str = ""

class TaskState(BaseModel):
    task_id: str = Field(default_factory=lambda: f"TASK-{str(uuid.uuid4())[:8].upper()}")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    original_prompt: str
    status: TaskStatus = TaskStatus.PENDING
    interpreted_goal: Optional[InterpretedGoal] = None
    plan: List[PlanStep] = Field(default_factory=list)
    current_step_index: int = 0
    discovered_facts: DiscoveredFacts = Field(default_factory=DiscoveredFacts)
    tool_history: List[ToolCallRecord] = Field(default_factory=list)
    approval_request: Optional[ApprovalRequest] = None
    verification_result: Optional[VerificationResult] = None
    evidence_bundle: Optional[EvidenceBundle] = None
    execution_logs: List[Dict[str, Any]] = Field(default_factory=list)
    error_history: List[Dict[str, Any]] = Field(default_factory=list)
    completion_summary: Optional[str] = None

    def log_event(self, event_type: str, message: str, details: Optional[Dict[str, Any]] = None):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "message": message,
            "current_step": self.current_step_index,
            "status": self.status.value,
            "details": details or {}
        }
        self.execution_logs.append(entry)
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def record_tool_call(self, record: ToolCallRecord):
        self.tool_history.append(record)
        self.log_event("TOOL_EXECUTION", f"Tool {record.tool_name} completed with {record.status}", {
            "tool": record.tool_name,
            "duration_ms": record.duration_ms,
            "status": record.status
        })

    def transition(self, new_status: TaskStatus, reason: str = ""):
        old_status = self.status
        self.status = new_status
        self.log_event("STATE_TRANSITION", f"Transitioned from {old_status.value} to {new_status.value}. {reason}".strip())
