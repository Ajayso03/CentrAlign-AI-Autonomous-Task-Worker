# CentrAlign AI Task Worker ? Demo Video Script & Storyboard

**Duration:** 2 Minutes 30 Seconds  
**Format:** Screen Recording with Voiceover  
**Target Audience:** CentrAlign AI Engineering Hiring Team  

---

## Storyboard & Timing Breakdown

### **0:00 ? 0:20 | Introduction & The Problem**
- **Visual:** Open on the CentrAlign Task Worker Web Console (`http://localhost:8000`). Show clean dark UI, top demo buttons, and architecture status badge.
- **Voiceover:**
  > *"Hi everyone! I?m presenting my submission for the CentrAlign AI Engineering Intern hiring challenge. We know that real enterprise AI employees can?t just be conversational chatbots that claim 'I would click here.' They need to understand business goals, navigate internal documents, operate enterprise software, recover when errors happen, obey corporate safety policies, and verify outcomes independently. Let's see that in action."*

---

### **0:20 ? 0:50 | Demo 1: Goal Understanding & The Happy Path**
- **Visual:** Click `[1. Happy Path ($4,850)]`. The prompt populates:
  `"Find the latest invoice from Acme under 5000, extract invoice number, amount, and due date, enter into finance, and verify."`
  Click `[Execute Autonomous Worker]`.
- **Action:** Watch the timeline light up in real time:
  1. `search_documents` scans the corporate document store.
  2. `inspect_and_select_latest` finds Acme invoice #1089 ($4,850.00).
  3. `policy_and_record_creation` checks AP-04 threshold (< $5,000, passes policy).
  4. `inspect_web_portal` checks DOM visibility.
  5. `verify_ground_truth` audits SQLite ledger.
- **Voiceover:**
  > *"Notice that I didn't give the worker a script of steps. I gave it a natural language objective. The agent parsed the target vendor, identified the latest document from several noisy files in our repository, verified that the amount was below our spending limit, posted it into our ERP, and generated a cryptographic SHA-256 evidence hash."*

---

### **0:50 ? 1:30 | Demo 2: Autonomous Error Recovery & Self-Healing**
- **Visual:** Click `[2. Self-Healing (Invalid Date)]`. The prompt populates:
  `"Find invoice 1099 from Acme, extract fields, enter into finance system, and verify."`
  Click `[Execute Autonomous Worker]`.
- **Action:**
  - In Step 3, the timeline shows an amber badge `? RECOVERED (Retries: 1)`.
  - Open the **Execution Logs** tab in the bottom drawer:
    Highlight `[FAILURE_DETECTED]: HTTP 422 Field due_date 'September 25, 2026' must be in strict ISO 8601 format`.
    Highlight `[AUTONOMOUS_SELF_HEALING]: Repaired due_date format from 'September 25, 2026' to ISO 8601 '2026-09-25'`.
    Highlight `[RECOVERY_SUCCEEDED]`.
- **Voiceover:**
  > *"Here is where real autonomy shines. Invoice 1099 had an unformatted date: 'September 25, 2026'. When submitted to our ERP, the schema validator rejected it with HTTP 422. Instead of crashing or reporting false success, the worker observed the error, classified it as a recoverable validation failure, normalized the date to ISO 8601, replanned the step, and successfully posted and verified it."*

---

### **1:30 ? 2:05 | Demo 3: Safe Human-in-the-Loop Policy Gate**
- **Visual:** Click `[3. Human Approval ($14,800)]`.
  Prompt: `"Find the latest invoice from Acme, extract fields, enter into finance, and verify."`
  Click `[Execute Autonomous Worker]`.
- **Action:**
  - Execution runs Steps 1 & 2.
  - The worker pauses. Status changes to `WAITING_FOR_APPROVAL`.
  - The purple **Human Approval Gateway** card appears on the right side:
    `Action: create_invoice_record` | `Amount: $14,800.00` | `Threshold: $5,000.00`.
  - Type note: `"Approved per Q3 infrastructure budget"`.
  - Click `[Approve]`.
  - The agent resumes live from Step 3 without restarting, completes the post, and verifies the outcome.
- **Voiceover:**
  > *"When an invoice exceeds our $5,000 threshold?like this enterprise GPU invoice for $14,800?our software-enforced policy engine halts execution. The agent serializes its state and waits for human sign-off. When I approve it, it resumes from the exact paused step without restarting from scratch. This demonstrates safe enterprise governance."*

---

### **2:05 ? 2:30 | Independent Verification & Evidence**
- **Visual:** Click the **Evidence** tab at the bottom.
  Show the `EvidenceBundle`:
  - ERP Record ID: `#3`
  - SHA-256 Audit Hash: `0fabcbdba...`
  - Click `[View ERP Portal]` to show the live HTML ledger in SQLite.
- **Voiceover:**
  > *"Finally, the agent never assumes tool success equals task success. It performs an independent read-after-write audit against the database, confirms every field, and produces this tamper-evident SHA-256 evidence bundle. The entire codebase is unit-tested, benchmarked, and ready to inspect. Thank you!"*
