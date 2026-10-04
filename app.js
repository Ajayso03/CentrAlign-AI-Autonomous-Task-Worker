
let activeTaskId = null;
let activeTaskData = null;

const SCENARIOS = {
    happy_path: {
        prompt: "Find the latest invoice from Acme under 5000, extract invoice number, amount, and due date, enter into finance, and verify.",
        reset_db: true,
        simulate_silent_drop: false
    },
    self_healing: {
        prompt: "Find invoice 1099 from Acme, extract fields, enter into finance system, and verify.",
        reset_db: true,
        simulate_silent_drop: false
    },
    human_approval: {
        prompt: "Find the latest invoice from Acme, extract the invoice number, amount, and due date, enter it into the finance system, and verify that it was saved.",
        reset_db: true,
        simulate_silent_drop: false
    },
    ambiguous: {
        prompt: "Find the latest invoice from Wayne Enterprises, extract the amount and due date, and enter it into the finance system.",
        reset_db: true,
        simulate_silent_drop: false
    },
    verification_fail: {
        prompt: "Find invoice 1089 from Acme, extract fields, enter into finance, and verify.",
        reset_db: true,
        simulate_silent_drop: true
    }
};

function loadScenario(key) {
    const s = SCENARIOS[key];
    if (!s) return;
    document.getElementById('prompt-input').value = s.prompt;
    document.getElementById('reset-db-toggle').checked = s.reset_db;
    window._current_scenario = key;
}

async function executeTask() {
    const prompt = document.getElementById('prompt-input').value.trim();
    if (!prompt) {
        alert("Please enter a task prompt.");
        return;
    }

    const resetDb = document.getElementById('reset-db-toggle').checked;
    const isVerificationFailDemo = (window._current_scenario === 'verification_fail');

    setLoading(true);
    updateSystemStatus("EXECUTING", "bg-indigo-500/20 text-indigo-300 border-indigo-500/40");

    try {
        const response = await fetch('/api/agent/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                prompt: prompt,
                reset_db_first: resetDb,
                simulate_silent_drop: Boolean(isVerificationFailDemo)
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error ${response.status}: ${await response.text()}`);
        }

        const taskState = await response.json();
        renderTaskState(taskState);
    } catch (err) {
        alert("Task execution failed: " + err.message);
    } finally {
        setLoading(false);
    }
}

async function submitApprovalDecision(approved) {
    if (!activeTaskId) return;
    const notes = document.getElementById('approval-notes').value.trim();

    try {
        const response = await fetch('/api/agent/approve', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                task_id: activeTaskId,
                approved: approved,
                user_name: "Alex Chen (Finance Director)",
                notes: notes || (approved ? "Approved via web console" : "Rejected via web console")
            })
        });

        if (!response.ok) {
            throw new Error(`Approval submission error: ${await response.text()}`);
        }

        const updatedState = await response.json();
        renderTaskState(updatedState);
    } catch (err) {
        alert("Approval failed: " + err.message);
    }
}

async function resetSandboxDB() {
    try {
        const res = await fetch('/api/sandbox/reset', { method: 'POST' });
        const data = await res.json();
        alert("Sandbox Database Reset: " + data.message);
    } catch (e) {
        alert("Failed to reset DB: " + e.message);
    }
}

function renderTaskState(state) {
    activeTaskId = state.task_id;
    activeTaskData = state;

    document.getElementById('current-task-id').innerText = state.task_id;

    if (state.interpreted_goal) {
        document.getElementById('state-goal').innerText = state.interpreted_goal.objective;
        document.getElementById('state-vendor').innerText = state.interpreted_goal.target_company || "None detected";
        const riskEl = document.getElementById('state-risk');
        riskEl.innerText = state.interpreted_goal.risk_level;
        if (state.interpreted_goal.risk_level === 'HIGH') {
            riskEl.className = "p-2 rounded bg-purple-950/60 border border-purple-500/40 text-purple-300 font-mono font-bold mt-1";
        } else {
            riskEl.className = "p-2 rounded bg-slate-950 border border-slate-800 text-slate-300 font-mono font-bold mt-1";
        }
    }

    const facts = state.discovered_facts || {};
    document.getElementById('fact-invoice-num').innerText = facts.invoice_number || "-";
    document.getElementById('fact-amount').innerText = facts.amount ? `$${facts.amount.toLocaleString(undefined, {minimumFractionDigits: 2})}` : "-";
    document.getElementById('fact-due-date').innerText = facts.due_date || facts.raw_due_date_text || "-";
    document.getElementById('fact-source-doc').innerText = facts.selected_document || "-";

    const verBox = document.getElementById('state-verification-box');
    if (state.verification_result) {
        const v = state.verification_result;
        if (v.is_verified) {
            verBox.className = "p-2 rounded bg-emerald-950/40 border border-emerald-500/30 text-emerald-300 font-mono mt-1 text-[11px] space-y-1";
            verBox.innerHTML = `<div class="font-bold">? 100% VERIFIED IN DB</div><div class="text-[10px] text-slate-400 break-all">Hash: ${v.evidence_hash}</div>`;
        } else {
            verBox.className = "p-2 rounded bg-rose-950/40 border border-rose-500/30 text-rose-300 font-mono mt-1 text-[11px] space-y-1";
            verBox.innerHTML = `<div class="font-bold">? VERIFICATION FAILED</div><div class="text-[10px] text-rose-400">${v.discrepancies.join('<br>')}</div>`;
        }
    } else {
        verBox.className = "p-2 rounded bg-slate-950 border border-slate-800 mt-1 text-[11px]";
        verBox.innerHTML = '<span class="text-slate-500 italic">Pending...</span>';
    }

    renderTimeline(state.plan, state.current_step_index);

    const approvalCard = document.getElementById('approval-card');
    if (state.status === "WAITING_FOR_APPROVAL" && state.approval_request) {
        approvalCard.classList.remove('hidden');
        document.getElementById('approval-summary').innerText = state.approval_request.summary;
        document.getElementById('approval-amount').innerText = `$${state.approval_request.amount?.toLocaleString(undefined, {minimumFractionDigits: 2})}`;
        updateSystemStatus("WAITING APPROVAL", "bg-purple-500/20 text-purple-300 border-purple-500/40");
    } else {
        approvalCard.classList.add('hidden');
        if (state.status === "COMPLETED") {
            updateSystemStatus("COMPLETED", "bg-emerald-500/20 text-emerald-300 border-emerald-500/40");
        } else if (state.status === "FAILED") {
            updateSystemStatus("FAILED / HALTED", "bg-rose-500/20 text-rose-300 border-rose-500/40");
        }
    }

    renderLogs(state.execution_logs);
    renderTools(state.tool_history);
    renderEvidence(state.evidence_bundle);
}

function renderTimeline(plan, currentIndex) {
    const container = document.getElementById('timeline-container');
    if (!plan || plan.length === 0) {
        container.innerHTML = '<div class="text-center py-12 text-slate-500 text-xs">No active plan generated.</div>';
        return;
    }

    let html = '';
    plan.forEach((step) => {
        let badgeColor = "bg-slate-800 text-slate-400 border-slate-700";
        let statusIcon = "?";
        let cardBorder = "border-slate-800";

        if (step.status === "SUCCESS") {
            badgeColor = "bg-emerald-950 text-emerald-400 border-emerald-500/40";
            statusIcon = "?";
            cardBorder = "border-emerald-500/30";
        } else if (step.status === "RECOVERED") {
            badgeColor = "bg-amber-950 text-amber-300 border-amber-500/40";
            statusIcon = "? RECOVERED";
            cardBorder = "border-amber-500/30";
        } else if (step.status === "IN_PROGRESS") {
            badgeColor = "bg-indigo-950 text-indigo-300 border-indigo-500/50";
            statusIcon = "? RUNNING";
            cardBorder = "border-indigo-500/50";
        } else if (step.status === "FAILED") {
            badgeColor = "bg-rose-950 text-rose-400 border-rose-500/40";
            statusIcon = "? FAILED";
            cardBorder = "border-rose-500/30";
        }

        html += `
        <div class="p-3 rounded-lg bg-slate-950/70 border ${cardBorder} flex items-start justify-between space-x-3">
            <div class="space-y-1">
                <div class="flex items-center space-x-2">
                    <span class="text-xs font-mono font-bold text-slate-300">Step ${step.step_id}</span>
                    <span class="text-xs font-semibold text-slate-200">${step.name}</span>
                </div>
                <div class="text-xs text-slate-400">${step.description}</div>
                <div class="text-[11px] text-slate-500 font-mono">Tool: <span class="text-indigo-400">${step.tool_name}</span></div>
            </div>
            <div class="text-right flex flex-col items-end space-y-1">
                <span class="text-[10px] px-2 py-0.5 rounded font-mono border ${badgeColor}">${statusIcon}</span>
                ${step.retry_count > 0 ? `<span class="text-[10px] text-amber-400 font-mono">Retries: ${step.retry_count}</span>` : ''}
            </div>
        </div>
        `;
    });
    container.innerHTML = html;
}

function renderLogs(logs) {
    const container = document.getElementById('tab-logs-content');
    document.getElementById('logs-count').innerText = `${logs ? logs.length : 0} events`;
    if (!logs || logs.length === 0) {
        container.innerHTML = '<div class="text-slate-500 italic">No events logged yet.</div>';
        return;
    }
    let html = '';
    logs.slice().reverse().forEach(log => {
        let tagColor = "text-slate-400";
        if (log.event_type.includes("SUCCESS") || log.event_type.includes("PASSED")) tagColor = "text-emerald-400 font-bold";
        else if (log.event_type.includes("HEALING") || log.event_type.includes("RECOVERY")) tagColor = "text-amber-400 font-bold";
        else if (log.event_type.includes("FAILED") || log.event_type.includes("ERROR")) tagColor = "text-rose-400 font-bold";
        else if (log.event_type.includes("APPROVAL")) tagColor = "text-purple-400 font-bold";

        html += `
        <div class="py-1 border-b border-slate-800/40 text-[11px] flex items-start space-x-3">
            <span class="text-slate-500 text-[10px] font-mono shrink-0">${log.timestamp.slice(11, 19)}</span>
            <span class="${tagColor} shrink-0 w-44 font-mono">[${log.event_type}]</span>
            <span class="text-slate-300 font-sans flex-1">${log.message}</span>
        </div>
        `;
    });
    container.innerHTML = html;
}

function renderTools(tools) {
    const container = document.getElementById('tab-tools-content');
    if (!tools || tools.length === 0) {
        container.innerHTML = '<div class="text-slate-500 italic">No tool calls executed.</div>';
        return;
    }
    let html = '';
    tools.forEach(t => {
        const isSuccess = t.status === "SUCCESS";
        html += `
        <div class="p-2 rounded bg-slate-950 border border-slate-800 text-[11px] space-y-0.5">
            <div class="flex justify-between items-center">
                <span class="font-bold text-indigo-400 font-mono">${t.tool_name}</span>
                <span class="text-[10px] font-mono ${isSuccess ? 'text-emerald-400' : 'text-rose-400'}">${t.status} (${t.duration_ms}ms)</span>
            </div>
            <div class="text-slate-400 text-[10px] font-mono truncate">Args: ${JSON.stringify(t.input_arguments)}</div>
        </div>
        `;
    });
    container.innerHTML = html;
}

function renderEvidence(evidence) {
    const container = document.getElementById('tab-evidence-content');
    if (!evidence) {
        container.innerHTML = '<div class="text-slate-500 italic">Evidence generated upon verification.</div>';
        return;
    }
    container.innerHTML = `
    <div class="p-3 bg-slate-950 rounded border border-slate-800 space-y-1 font-mono text-xs">
        <div class="text-indigo-400 font-bold">CRYPTOGRAPHIC EVIDENCE BUNDLE</div>
        <div class="text-slate-300">Task ID: ${evidence.task_id}</div>
        <div class="text-slate-300">Record ID: #${evidence.erp_record_id}</div>
        <div class="text-emerald-400 break-all">SHA-256: ${evidence.verification_hash}</div>
        <div class="text-slate-300 font-sans mt-2">${evidence.completion_summary}</div>
    </div>
    `;
}

function switchTab(tab) {
    ['logs', 'tools', 'evidence'].forEach(t => {
        document.getElementById(`tab-${t}-content`).classList.add('hidden');
        document.getElementById(`tab-${t}-btn`).className = "px-2.5 py-1 text-xs rounded text-slate-400";
    });
    document.getElementById(`tab-${tab}-content`).classList.remove('hidden');
    document.getElementById(`tab-${tab}-btn`).className = "px-2.5 py-1 text-xs rounded bg-slate-800 text-indigo-400 border border-indigo-500/30";
}

function updateSystemStatus(text, classes) {
    const el = document.getElementById('system-status-badge');
    el.className = `flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-mono border ${classes}`;
    el.innerHTML = `<span class="w-2 h-2 rounded-full bg-current"></span><span>${text}</span>`;
}

function setLoading(isLoading) {
    const btn = document.getElementById('run-task-btn');
    const icon = document.getElementById('run-icon');
    const txt = document.getElementById('run-text');
    if (isLoading) {
        btn.disabled = true;
        icon.innerText = "?";
        txt.innerText = "Running...";
    } else {
        btn.disabled = false;
        icon.innerText = "?";
        txt.innerText = "Execute Autonomous Worker";
    }
}
