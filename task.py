from __future__ import annotations

import html
import json
import os
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import gradio as gr


TASK_UI_CSS = """
#task-tab {
  min-height: calc(100dvh - 72px);
}
#task-layout {
  min-height: calc(100dvh - 150px);
  gap: 16px;
}
#task-sidebar,
#task-main {
  min-height: 0;
}
#task-sidebar .gradio-markdown,
#task-main .gradio-markdown {
  margin-bottom: 0;
}
#task-selector {
  gap: 10px;
}
#task-selector label {
  display: block;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  padding: 12px 14px;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
  transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
}
#task-selector label:hover {
  border-color: #cbd5e1;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
  transform: translateY(-1px);
}
#task-selector label:has(input:checked) {
  border-color: #0f766e;
  background: #f0fdfa;
  box-shadow: 0 14px 30px rgba(15, 118, 110, 0.14);
}
#task-selector label span {
  white-space: pre-line;
  line-height: 1.45;
}
#task-selector input {
  margin-top: 3px;
}
.task-card {
  border: 1px solid #e5e7eb;
  border-radius: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #fbfbf8 100%);
  padding: 16px 18px;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06);
}
.task-card + .task-card {
  margin-top: 12px;
}
.task-title-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
.task-title-row h2,
.task-title-row h3 {
  margin: 0;
}
.task-meta {
  margin-top: 10px;
  display: grid;
  gap: 8px;
}
.task-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 12px;
}
.task-kv {
  border: 1px solid #ece7dc;
  border-radius: 14px;
  padding: 10px 12px;
  background: rgba(250, 248, 242, 0.82);
}
.task-kv-label {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 4px;
}
.task-kv-value {
  font-size: 14px;
  color: #111827;
  font-weight: 600;
}
.task-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 5px 10px;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}
.task-badge-draft { background: #f3f4f6; color: #4b5563; }
.task-badge-planning { background: #e0f2fe; color: #075985; }
.task-badge-in-progress { background: #dcfce7; color: #166534; }
.task-badge-waiting-on-me { background: #fef3c7; color: #92400e; }
.task-badge-waiting-on-others { background: #e0e7ff; color: #3730a3; }
.task-badge-blocked { background: #fee2e2; color: #991b1b; }
.task-badge-done { background: #d1fae5; color: #065f46; }
.task-badge-failed { background: #fee2e2; color: #991b1b; }
.task-chip-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
}
.task-chip {
  border: 1px solid #ddd6c8;
  border-radius: 999px;
  padding: 5px 10px;
  font-size: 12px;
  color: #4b5563;
  background: #faf8f2;
}
.task-timeline {
  display: grid;
  gap: 12px;
}
.task-event {
  border-left: 3px solid #d6cbb7;
  padding-left: 12px;
}
.task-event-time {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 4px;
}
.task-event-title {
  font-weight: 700;
  color: #111827;
  margin-bottom: 4px;
}
.task-event-body {
  color: #374151;
  font-size: 14px;
  line-height: 1.45;
}
.task-list {
  display: grid;
  gap: 10px;
}
.task-list-item {
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  padding: 12px;
  background: #fff;
}
.task-panel-stack {
  display: grid;
  gap: 12px;
}
.task-progress-shell {
  margin-top: 14px;
  border-radius: 999px;
  height: 12px;
  background: #ece7dc;
  overflow: hidden;
}
.task-progress-bar {
  height: 100%;
  background: linear-gradient(90deg, #0f766e 0%, #14b8a6 100%);
  border-radius: 999px;
}
.task-progress-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-top: 10px;
  font-size: 13px;
  color: #4b5563;
}
.task-list-item-title {
  font-weight: 700;
  color: #111827;
  margin-bottom: 6px;
}
.task-list-item-text {
  color: #4b5563;
  font-size: 13px;
  line-height: 1.45;
}
.task-empty {
  color: #6b7280;
  font-style: italic;
}
@media (max-width: 1024px) {
  #task-layout {
    flex-direction: column;
  }
  .task-grid {
    grid-template-columns: 1fr;
  }
}
"""


def _escape(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _status_slug(status: str) -> str:
    return str(status).strip().lower().replace(" ", "-")


def _status_badge(status: str) -> str:
    slug = _status_slug(status)
    return f'<span class="task-badge task-badge-{slug}">{_escape(status)}</span>'


def _status_progress(status: str) -> int:
    progress_map = {
        "draft": 10,
        "planning": 25,
        "in-progress": 60,
        "waiting-on-me": 75,
        "waiting-on-others": 70,
        "blocked": 45,
        "done": 100,
        "failed": 100,
    }
    return progress_map.get(_status_slug(status), 20)


def _task_progress(task: Optional[Dict[str, Any]]) -> int:
    if not task:
        return 0
    raw_progress = task.get("progress")
    if isinstance(raw_progress, (int, float)):
        return max(0, min(100, int(raw_progress)))
    return _status_progress(str(task.get("status", "Draft")))


def _discover_task_files(task_root: str) -> List[str]:
    if not os.path.isdir(task_root):
        return []
    files = []
    for name in sorted(os.listdir(task_root)):
        if name.lower().endswith(".json"):
            files.append(os.path.join(task_root, name))
    return files


def _task_file_choices(task_root: str) -> List[Tuple[str, str]]:
    choices = []
    for path in _discover_task_files(task_root):
        choices.append((os.path.basename(path), path))
    return choices


def _normalize_task(task: Dict[str, Any], index: int) -> Dict[str, Any]:
    normalized = deepcopy(task)
    normalized.setdefault("id", f"task-{index + 1}")
    normalized.setdefault("title", f"Task {index + 1}")
    normalized.setdefault("status", "Draft")
    normalized.setdefault("priority", "Medium")
    normalized.setdefault("owner", "Agent")
    normalized.setdefault("goal", "")
    normalized.setdefault("deadline", "")
    normalized.setdefault("last_update", "")
    normalized.setdefault("next_action", "")
    normalized.setdefault("current_step", "")
    normalized.setdefault("why", "")
    normalized.setdefault("risk_level", "Low")
    normalized.setdefault("timeline", [])
    normalized.setdefault("approvals", [])
    normalized.setdefault("constraints", {})
    normalized.setdefault("artifacts", [])
    normalized.setdefault("chat", [])
    normalized.setdefault("latest_result", "")
    return normalized


def _load_tasks(task_file: Optional[str]) -> List[Dict[str, Any]]:
    if not task_file or not os.path.exists(task_file):
        return []
    with open(task_file, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    tasks = payload.get("tasks", []) if isinstance(payload, dict) else payload
    if not isinstance(tasks, list):
        return []
    return [_normalize_task(task, index) for index, task in enumerate(tasks) if isinstance(task, dict)]


def _find_task(tasks: List[Dict[str, Any]], task_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not tasks:
        return None
    for task in tasks:
        if task.get("id") == task_id:
            return task
    return tasks[0]


def _task_choices(tasks: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
    return [
        (
            "\n".join(
                [
                    str(task.get("title", "Untitled")),
                    f"Status: {task.get('status', 'Draft')} | Priority: {task.get('priority', 'Medium')}",
                    f"Next: {str(task.get('next_action') or 'No next action set')[:90]}",
                ]
            ),
            task.get("id", ""),
        )
        for task in tasks
    ]


def _append_timeline(task: Dict[str, Any], title: str, details: str) -> None:
    timestamp = datetime.now().astimezone().strftime("%b %d, %I:%M %p")
    task.setdefault("timeline", []).insert(
        0,
        {
            "time": timestamp,
            "summary": title,
            "details": details,
        },
    )
    task["last_update"] = timestamp


def _render_inbox(tasks: List[Dict[str, Any]]) -> str:
    if not tasks:
        return '<div class="task-card"><div class="task-empty">No tasks loaded.</div></div>'
    status_counts: Dict[str, int] = {}
    for task in tasks:
        status = task.get("status", "Draft")
        status_counts[status] = status_counts.get(status, 0) + 1
    cards = []
    for task in tasks:
        approval_needed = any(a.get("status", "pending") == "pending" for a in task.get("approvals", []))
        approval_chip = '<span class="task-chip">Approval needed</span>' if approval_needed else ""
        cards.append(
            f"""
            <div class="task-list-item">
              <div class="task-list-item-title">{_escape(task.get("title"))}</div>
              <div class="task-list-item-text">Next: {_escape(task.get("next_action") or "No next action set")}</div>
              <div class="task-chip-row">
                {_status_badge(task.get("status", "Draft"))}
                <span class="task-chip">Priority: {_escape(task.get("priority", "Medium"))}</span>
                <span class="task-chip">Updated: {_escape(task.get("last_update", "Unknown"))}</span>
                {approval_chip}
              </div>
            </div>
            """
        )
    counts = " ".join(
        f'<span class="task-chip">{_escape(status)}: {count}</span>'
        for status, count in status_counts.items()
    )
    return f'<div class="task-card"><div class="task-list">{cards and "".join(cards) or ""}</div><div class="task-chip-row">{counts}</div></div>'


def _render_header(task: Optional[Dict[str, Any]]) -> str:
    if not task:
        return '<div class="task-card"><div class="task-empty">Select a task to view details.</div></div>'
    progress = _task_progress(task)
    return f"""
    <div class="task-card">
      <div class="task-title-row">
        <div>
          <h2>{_escape(task.get("title"))}</h2>
          <div class="task-meta">{_escape(task.get("goal") or "No goal provided.")}</div>
        </div>
        {_status_badge(task.get("status", "Draft"))}
      </div>
      <div class="task-progress-shell">
        <div class="task-progress-bar" style="width: {progress}%;"></div>
      </div>
      <div class="task-progress-meta">
        <span>Progress: {progress}%</span>
        <span>Current step: {_escape(task.get("current_step") or "Not set")}</span>
      </div>
      <div class="task-chip-row">
        <span class="task-chip">Priority: {_escape(task.get("priority", "Medium"))}</span>
        <span class="task-chip">Owner: {_escape(task.get("owner", "Agent"))}</span>
        <span class="task-chip">Deadline: {_escape(task.get("deadline", "None"))}</span>
        <span class="task-chip">Last update: {_escape(task.get("last_update", "Unknown"))}</span>
      </div>
    </div>
    """


def _render_current_state(task: Optional[Dict[str, Any]]) -> str:
    if not task:
        return '<div class="task-card"><div class="task-empty">No task selected.</div></div>'
    return f"""
    <div class="task-card">
      <div class="task-title-row"><h3>Current State</h3></div>
      <div class="task-grid">
        <div class="task-kv">
          <div class="task-kv-label">Current step</div>
          <div class="task-kv-value">{_escape(task.get("current_step") or "Not set")}</div>
        </div>
        <div class="task-kv">
          <div class="task-kv-label">Risk level</div>
          <div class="task-kv-value">{_escape(task.get("risk_level") or "Low")}</div>
        </div>
        <div class="task-kv">
          <div class="task-kv-label">Why</div>
          <div class="task-kv-value">{_escape(task.get("why") or "No rationale provided")}</div>
        </div>
        <div class="task-kv">
          <div class="task-kv-label">Next planned action</div>
          <div class="task-kv-value">{_escape(task.get("next_action") or "No next action")}</div>
        </div>
      </div>
    </div>
    """


def _render_timeline(task: Optional[Dict[str, Any]]) -> str:
    if not task:
        return '<div class="task-card"><div class="task-empty">No timeline yet.</div></div>'
    events = task.get("timeline", [])
    if not events:
        return '<div class="task-card"><h3>Timeline</h3><div class="task-empty">No timeline entries yet.</div></div>'
    items = []
    for event in events:
        items.append(
            f"""
            <div class="task-event">
              <div class="task-event-time">{_escape(event.get("time", ""))}</div>
              <div class="task-event-title">{_escape(event.get("summary", "Update"))}</div>
              <div class="task-event-body">{_escape(event.get("details", ""))}</div>
            </div>
            """
        )
    return f'<div class="task-card"><h3>Timeline</h3><div class="task-timeline">{"".join(items)}</div></div>'


def _render_approvals(task: Optional[Dict[str, Any]]) -> str:
    if not task:
        return '<div class="task-card"><div class="task-empty">No approval data.</div></div>'
    approvals = task.get("approvals", [])
    pending = [approval for approval in approvals if approval.get("status", "pending") == "pending"]
    if not pending:
        return '<div class="task-card"><h3>Needs Approval</h3><div class="task-empty">No pending approvals.</div></div>'
    cards = []
    for approval in pending:
        cards.append(
            f"""
            <div class="task-list-item">
              <div class="task-list-item-title">{_escape(approval.get("title", "Approval needed"))}</div>
              <div class="task-list-item-text">{_escape(approval.get("reason", ""))}</div>
            </div>
            """
        )
    return f'<div class="task-card"><h3>Needs Approval</h3><div class="task-list">{"".join(cards)}</div></div>'


def _render_next_action(task: Optional[Dict[str, Any]]) -> str:
    if not task:
        return '<div class="task-card"><div class="task-empty">No task selected.</div></div>'
    return f"""
    <div class="task-card">
      <h3>Next Action</h3>
      <div class="task-list-item-text">{_escape(task.get("next_action") or "No next action set.")}</div>
    </div>
    """


def _render_artifacts(task: Optional[Dict[str, Any]]) -> str:
    if not task:
        return '<div class="task-card"><div class="task-empty">No artifacts.</div></div>'
    artifacts = task.get("artifacts", [])
    if not artifacts:
        return '<div class="task-card"><h3>Artifacts</h3><div class="task-empty">No artifacts attached.</div></div>'
    items = []
    for artifact in artifacts:
        items.append(
            f"""
            <div class="task-list-item">
              <div class="task-list-item-title">{_escape(artifact.get("name", "Artifact"))}</div>
              <div class="task-list-item-text">{_escape(artifact.get("summary", ""))}</div>
            </div>
            """
        )
    return f'<div class="task-card"><h3>Artifacts / Evidence</h3><div class="task-list">{"".join(items)}</div></div>'


def _render_constraints(task: Optional[Dict[str, Any]]) -> str:
    if not task:
        return "{}"
    return json.dumps(task.get("constraints", {}), indent=2, ensure_ascii=False)


def _render_chat(task: Optional[Dict[str, Any]]) -> List[Dict[str, str]]:
    if not task:
        return []
    messages = []
    for message in task.get("chat", []):
        role = message.get("role", "assistant")
        content = message.get("content", "")
        messages.append({"role": role, "content": content})
    return messages


def _render_latest_result(task: Optional[Dict[str, Any]]) -> str:
    if not task:
        return '<div class="task-card"><h3>Latest Result</h3><div class="task-empty">No task selected.</div></div>'
    latest_result = str(task.get("latest_result") or "").strip()
    if not latest_result:
        return '<div class="task-card"><h3>Latest Result</h3><div class="task-empty">No run result yet.</div></div>'
    return f"""
    <div class="task-card">
      <h3>Latest Result</h3>
      <div class="task-list-item-text">{_escape(latest_result)}</div>
    </div>
    """


def _build_demo_result(task: Dict[str, Any]) -> str:
    title = str(task.get("title", "Task"))
    now = datetime.now().astimezone()
    timestamp = now.strftime("%b %d, %I:%M %p")

    if task.get("id") == "daily-stock-market-summary-5pm":
        return (
            f"{timestamp} market wrap: S&P 500 finished slightly higher, Nasdaq outperformed, "
            "and the Dow was roughly flat. Tech and semiconductors led gains while defensives lagged. "
            "The main drivers were late-session buying, rate-cut expectations, and a handful of large-cap earnings headlines. "
            "This is a demo task result for the example workflow."
        )

    next_action = str(task.get("next_action") or "No next action set.")
    current_step = str(task.get("current_step") or "No current step.")
    return (
        f"{timestamp} task run completed for '{title}'. "
        f"Current step: {current_step}. Next action: {next_action}. "
        "This is a demo execution result."
    )


def _dashboard_payload(
    tasks: List[Dict[str, Any]],
    selected_id: Optional[str],
    action_note: str = "",
):
    task = _find_task(tasks, selected_id)
    resolved_id = task.get("id") if task else None
    return (
        tasks,
        resolved_id,
        gr.update(choices=_task_choices(tasks), value=resolved_id),
        _render_header(task),
        _render_approvals(task),
        _render_timeline(task),
        _render_artifacts(task),
        _render_chat(task),
    )


def _load_task_file_for_ui(task_file: Optional[str]):
    tasks = _load_tasks(task_file)
    selected_id = tasks[0]["id"] if tasks else None
    return _dashboard_payload(tasks, selected_id, action_note=f"Loaded {os.path.basename(task_file) if task_file else 'no file'}.")


def _select_task_for_ui(task_id: Optional[str], tasks: List[Dict[str, Any]]):
    return _dashboard_payload(tasks or [], task_id)


def _update_task_status(tasks: List[Dict[str, Any]], task_id: Optional[str], status: str, step: str, note: str):
    tasks = deepcopy(tasks or [])
    task = _find_task(tasks, task_id)
    if not task:
        return _dashboard_payload(tasks, task_id, action_note="No task selected.")
    task["status"] = status
    task["current_step"] = step
    _append_timeline(task, note, f"Status changed to {status}.")
    return _dashboard_payload(tasks, task.get("id"), action_note=note)


def _approve_selected(tasks: List[Dict[str, Any]], task_id: Optional[str]):
    tasks = deepcopy(tasks or [])
    task = _find_task(tasks, task_id)
    if not task:
        return _dashboard_payload(tasks, task_id, action_note="No task selected.")
    approvals = task.get("approvals", [])
    changed = False
    for approval in approvals:
        if approval.get("status", "pending") == "pending":
            approval["status"] = "approved"
            changed = True
    if changed:
        task["status"] = "In progress"
        task["current_step"] = "Approved by user"
        _append_timeline(task, "Approval granted", "User approved the next planned action.")
        note = "Approved next step."
    else:
        note = "No pending approvals to approve."
    return _dashboard_payload(tasks, task.get("id"), action_note=note)


def _save_constraints(tasks: List[Dict[str, Any]], task_id: Optional[str], constraints_text: str):
    tasks = deepcopy(tasks or [])
    task = _find_task(tasks, task_id)
    if not task:
        return _dashboard_payload(tasks, task_id, action_note="No task selected.")
    try:
        parsed = json.loads(constraints_text or "{}")
    except json.JSONDecodeError as exc:
        return _dashboard_payload(tasks, task.get("id"), action_note=f"Invalid constraints JSON: {exc}")
    if not isinstance(parsed, dict):
        return _dashboard_payload(tasks, task.get("id"), action_note="Constraints must be a JSON object.")
    task["constraints"] = parsed
    _append_timeline(task, "Constraints updated", "User edited task constraints.")
    return _dashboard_payload(tasks, task.get("id"), action_note="Constraints saved.")


def _append_chat_message(tasks: List[Dict[str, Any]], task_id: Optional[str], message: str):
    tasks = deepcopy(tasks or [])
    task = _find_task(tasks, task_id)
    if not task:
        payload = _dashboard_payload(tasks, task_id, action_note="No task selected.")
        return (*payload, "")
    text = (message or "").strip()
    if not text:
        payload = _dashboard_payload(tasks, task.get("id"))
        return (*payload, "")
    task.setdefault("chat", []).append({"role": "user", "content": text})
    _append_timeline(task, "User update", text)
    payload = _dashboard_payload(tasks, task.get("id"), action_note="Task chat updated.")
    return (*payload, "")


def _run_selected_task(tasks: List[Dict[str, Any]], task_id: Optional[str]):
    tasks = deepcopy(tasks or [])
    task = _find_task(tasks, task_id)
    if not task:
        return _dashboard_payload(tasks, task_id, action_note="No task selected.")

    result = _build_demo_result(task)
    task["latest_result"] = result
    task["status"] = "In progress" if _status_slug(str(task.get("status", ""))) not in {"done", "failed"} else task.get("status", "Done")
    task["current_step"] = "Last run completed"
    task.setdefault("chat", []).append({"role": "assistant", "content": result})
    _append_timeline(task, "Task run completed", result)
    return _dashboard_payload(tasks, task.get("id"), action_note="Task ran successfully.")


def build_task_tab(task_root: str) -> None:
    task_file_choices = _task_file_choices(task_root)
    default_task_file = task_file_choices[0][1] if task_file_choices else None
    initial_tasks = _load_tasks(default_task_file)
    initial_selected_id = initial_tasks[0]["id"] if initial_tasks else None

    (
        _,
        _selected_task_id,
        initial_selector_update,
        initial_header,
        initial_approvals,
        initial_timeline,
        initial_artifacts,
        initial_chat,
    ) = _dashboard_payload(initial_tasks, initial_selected_id)

    task_file_state = gr.State(default_task_file)
    tasks_state = gr.State(initial_tasks)
    selected_task_state = gr.State(_selected_task_id)

    with gr.Row(elem_id="task-layout"):
        with gr.Column(scale=1, min_width=280, elem_id="task-sidebar"):
            refresh_tasks = gr.Button("Reload Tasks")
            task_selector = gr.Radio(
                choices=initial_selector_update.get("choices", []),
                value=initial_selector_update.get("value"),
                label="All Tasks",
                interactive=True,
                elem_id="task-selector",
            )
        with gr.Column(scale=3, min_width=640, elem_id="task-main"):
            with gr.Column(elem_classes="task-panel-stack"):
                task_header = gr.HTML(initial_header)
                task_approvals = gr.HTML(initial_approvals)
                with gr.Row():
                    run_task = gr.Button("Run Task", variant="primary")
                    pause_task = gr.Button("Pause")
                    cancel_task = gr.Button("Cancel Task")
                    approve_next = gr.Button("Approve Next Step")
                task_timeline = gr.HTML(initial_timeline)
                task_artifacts = gr.HTML(initial_artifacts)
                task_chat = gr.Chatbot(label="Task Chat", height=320, value=initial_chat)
                with gr.Row():
                    task_chat_input = gr.Textbox(
                        show_label=False,
                        placeholder="Update this task...",
                        lines=2,
                        scale=4,
                    )
                    task_chat_send = gr.Button("Send", variant="primary")

    dashboard_outputs = [
        tasks_state,
        selected_task_state,
        task_selector,
        task_header,
        task_approvals,
        task_timeline,
        task_artifacts,
        task_chat,
    ]

    refresh_tasks.click(
        fn=_load_task_file_for_ui,
        inputs=task_file_state,
        outputs=dashboard_outputs,
    )
    task_selector.change(
        fn=_select_task_for_ui,
        inputs=[task_selector, tasks_state],
        outputs=dashboard_outputs,
    )
    run_task.click(
        fn=_run_selected_task,
        inputs=[tasks_state, selected_task_state],
        outputs=dashboard_outputs,
    )
    pause_task.click(
        fn=lambda tasks, task_id: _update_task_status(tasks, task_id, "Blocked", "Paused by user", "Task paused"),
        inputs=[tasks_state, selected_task_state],
        outputs=dashboard_outputs,
    )
    cancel_task.click(
        fn=lambda tasks, task_id: _update_task_status(tasks, task_id, "Failed", "Cancelled by user", "Task cancelled"),
        inputs=[tasks_state, selected_task_state],
        outputs=dashboard_outputs,
    )
    approve_next.click(
        fn=_approve_selected,
        inputs=[tasks_state, selected_task_state],
        outputs=dashboard_outputs,
    )
    task_chat_send.click(
        fn=_append_chat_message,
        inputs=[tasks_state, selected_task_state, task_chat_input],
        outputs=dashboard_outputs + [task_chat_input],
    )
    task_chat_input.submit(
        fn=_append_chat_message,
        inputs=[tasks_state, selected_task_state, task_chat_input],
        outputs=dashboard_outputs + [task_chat_input],
    )
