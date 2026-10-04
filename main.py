"""
Master API Server for CentrAlign Autonomous AI Task Worker.
Exposes Agent endpoints, mounts Sandbox ERP, and serves the Web Console UI.
"""

import os
from typing import Dict, Any, Optional
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.agent.executor import TaskExecutionWorker
from app.agent.state import TaskState, TaskStatus
from app.sandbox.erp_server import erp_app, reset_database, get_db

# Initialize master application
app = FastAPI(
    title="CentrAlign Autonomous AI Task Worker",
    description="Enterprise AI Worker with Real Execution, Self-Healing, Human Approval, and Verification",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for active tasks
ACTIVE_TASKS: Dict[str, TaskState] = {}
WORKER = TaskExecutionWorker()

class RunTaskRequest(BaseModel):
    prompt: str
    reset_db_first: bool = False
    simulate_transient_error: bool = False
    simulate_silent_drop: bool = False

class ApprovalDecisionRequest(BaseModel):
    task_id: str
    approved: bool
    user_name: str = "Finance Manager"
    notes: str = ""

@app.post("/api/agent/run")
def run_task(req: RunTaskRequest):
    if req.reset_db_first:
        reset_database()

    # Handle simulation configs
    from app.sandbox.erp_server import set_transient_error, set_silent_drop
    if req.simulate_transient_error:
        set_transient_error(1)
    if req.simulate_silent_drop:
        set_silent_drop(True)

    state = WORKER.start_task(req.prompt)
    ACTIVE_TASKS[state.task_id] = state
    return state.model_dump()

@app.post("/api/agent/approve")
def approve_task(req: ApprovalDecisionRequest):
    state = ACTIVE_TASKS.get(req.task_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Task {req.task_id} not found.")

    if state.status != TaskStatus.WAITING_FOR_APPROVAL:
        raise HTTPException(
            status_code=400,
            detail=f"Task {req.task_id} is in status '{state.status.value}', not WAITING_FOR_APPROVAL."
        )

    resumed_state = WORKER.resume_with_approval(
        state=state,
        approved=req.approved,
        user_name=req.user_name,
        notes=req.notes
    )
    ACTIVE_TASKS[resumed_state.task_id] = resumed_state
    return resumed_state.model_dump()

@app.get("/api/agent/tasks/{task_id}")
def get_task(task_id: str):
    state = ACTIVE_TASKS.get(task_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")
    return state.model_dump()

@app.get("/api/agent/tasks")
def list_tasks():
    return [{"task_id": tid, "status": t.status.value, "created_at": t.created_at} for tid, t in ACTIVE_TASKS.items()]

@app.post("/api/sandbox/reset")
def reset_sandbox():
    reset_database()
    return {"status": "SUCCESS", "message": "Sandbox ERP database cleared."}

# Mount Sandbox ERP endpoints under /api/v1
for route in erp_app.routes:
    app.routes.append(route)

# Mount frontend static directory
frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

@app.get("/")
def serve_index():
    index_file = os.path.join(os.path.dirname(__file__), "frontend", "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "CentrAlign AI Worker API Running. Frontend directory not found."}

if __name__ == "__main__":
    import uvicorn
    print("Starting CentrAlign Task Worker on http://localhost:8000")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
