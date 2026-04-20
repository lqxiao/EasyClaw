from __future__ import annotations
import html
import json
import os
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple
import uuid
from apis import _provider_map
import gradio as gr
import yaml
from memory import RagMemoryStore
from agent import AutoAgent

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
#task-selector {
  gap: 10px;
}
#task-selector label {
  display: block;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  padding: 10px 12px;
  background: #ffffff;
}
#task-selector label:has(input:checked) {
  border-color: #0f766e;
  background: #f0fdfa;
}
#task-selector label span {
  white-space: pre-line;
  line-height: 1.4;
}
.task-card {
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  background: #ffffff;
  padding: 16px;
}
.task-card h2 {
  margin: 0 0 8px;
}
.task-card p {
  margin: 0;
  color: #374151;
  line-height: 1.5;
}
.task-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
}
.task-chip {
  border: 1px solid #d1d5db;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  color: #4b5563;
  background: #f9fafb;
}
.task-row {
  margin-top: 12px;
}
.task-label {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 4px;
}
.task-value {
  color: #111827;
  line-height: 1.5;
}
.task-empty {
  color: #6b7280;
  font-style: italic;
}
@media (max-width: 1024px) {
  #task-layout {
    flex-direction: column;
  }
}
"""


def _escape(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _discover_task_files(task_root: str) -> List[str]:
    if not os.path.isdir(task_root):
        return []

    preferred: List[str] = []
    fallback: List[str] = []
    for root, _, files in os.walk(task_root):
        for name in sorted(files):
            if not name.lower().endswith(".json"):
                continue
            path = os.path.join(root, name)
            if name == "task.json":
                preferred.append(path)
            else:
                fallback.append(path)
    return sorted(preferred) + sorted(fallback)


def _normalize_task(task: Dict[str, Any], index: int, source_file: str) -> Dict[str, Any]:
    normalized = deepcopy(task)
    normalized.setdefault("id", f"task-{index + 1}")
    normalized.setdefault("title", f"Task {index + 1}")
    normalized.setdefault("status", "Draft")
    normalized.setdefault("priority", "Medium")
    normalized.setdefault("goal", "")
    normalized.setdefault("period", "no repeat")
    normalized.setdefault("next_action", "")
    normalized.setdefault("current_step", "")
    normalized.setdefault("approvals", [])
    normalized["_source_file"] = source_file
    return normalized


def _load_tasks(task_root: str) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    for index, path in enumerate(_discover_task_files(task_root)):
        with open(path, "r", encoding="utf-8") as handle:
            task = json.load(handle)
            tasks.append(_normalize_task(task, index, path))
    return tasks

def _find_task(tasks: List[Dict[str, Any]], task_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not tasks:
        return None
    for task in tasks:
        if task.get("id") == task_id:
            return task
    return tasks[0]

def _task_choices(tasks: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
    choices = []
    for task in tasks:
        choices.append(
            (
                "\n".join(
                    [
                        str(task.get("title", "Untitled")),
                        f"{task.get('status', 'Draft')} | {task.get('priority', 'Medium')}",
                    ]
                ),
                str(task.get("id", "")),
            )
        )
    return choices


def _task_summary(task: Optional[Dict[str, Any]]) -> str:
    if not task:
        return '<div class="task-card"><div class="task-empty">No tasks found.</div></div>'

    approvals = task.get("approvals", [])
    pending_approvals = sum(1 for approval in approvals if approval.get("status", "pending") == "pending")
    source_file = os.path.relpath(str(task.get("_source_file", "")), os.getcwd())

    return f"""
    <div class="task-card">
      <h2>{_escape(task.get("title"))}</h2>
      <p>{_escape(task.get("goal") or "No goal provided.")}</p>
      <div class="task-meta">
        <span class="task-chip">Status: {_escape(task.get("status", "Draft"))}</span>
        <span class="task-chip">Priority: {_escape(task.get("priority", "Medium"))}</span>
        <span class="task-chip">Period: {_escape(task.get("period", "no repeat"))}</span>
      </div>
      <div class="task-row">
        <div class="task-label">Next Action</div>
        <div class="task-value">{_escape(task.get("next_action") or "No next action set.")}</div>
      </div>
      <div class="task-row">
        <div class="task-label">Current Step</div>
        <div class="task-value">{_escape(task.get("current_step") or "Not set")}</div>
      </div>
      <div class="task-row">
        <div class="task-label">Pending Approvals</div>
        <div class="task-value">{pending_approvals}</div>
      </div>
      <div class="task-row">
        <div class="task-label">Source</div>
        <div class="task-value">{_escape(source_file)}</div>
      </div>
    </div>
    """


def _task_json_payload(task: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not task:
        return {}
    payload = deepcopy(task)
    # payload.pop("_source_file", None)
    return payload


def _task_view_payload(tasks: List[Dict[str, Any]], selected_id: Optional[str]):
    task = _find_task(tasks, selected_id)
    resolved_id = task.get("id") if task else None
    return [
        tasks,
        resolved_id,
        gr.update(choices=_task_choices(tasks), value=resolved_id),
        _task_summary(task),
        _task_json_payload(task),
    ]


def _reload_tasks_for_ui(task_root: str):
    tasks = _load_tasks(task_root)
    selected_id = tasks[0]["id"] if tasks else None
    return _task_view_payload(tasks, selected_id)


def _select_task_for_ui(task_id: Optional[str], tasks: List[Dict[str, Any]]):
    return _task_view_payload(tasks or [], task_id)


def build_task_tab(task_root: str) -> None:
    initial_tasks = _load_tasks(task_root)
    initial_selected_id = initial_tasks[0]["id"] if initial_tasks else None
    (
        _,
        initial_task_id,
        initial_selector_update,
        initial_summary,
        initial_json,
    ) = _task_view_payload(initial_tasks, initial_selected_id)

    tasks_state = gr.State(initial_tasks)
    selected_task_state = gr.State(initial_task_id)
    task_root = gr.State(task_root)

    with gr.Row(elem_id="task-layout"):
        with gr.Column(scale=1, min_width=280, elem_id="task-sidebar"):
            refresh_tasks = gr.Button("Reload")
            task_selector = gr.Radio(
                choices=initial_selector_update.get("choices", []),
                value=initial_selector_update.get("value"),
                label="Tasks",
                interactive=True,
                elem_id="task-selector",
            )
        with gr.Column(scale=2, min_width=520, elem_id="task-main"):
            task_summary = gr.HTML(initial_summary)
            run_it_now = gr.Button("Run it now")
            chatbot = gr.Chatbot(
                    show_label=False,
                    elem_id="chatbot",
                    scale=2,
                    height="100%",
                    min_height=800,
                    layout="bubble",
                    placeholder="",
                    container=False
            )
            task_json = gr.JSON(value=initial_json, label="task.json")
    outputs = [tasks_state, selected_task_state, task_selector, task_summary, task_json]

    refresh_tasks.click(
        fn=_reload_tasks_for_ui,
        inputs=[task_root],
        outputs=outputs,
    )
    task_selector.change(
        fn=_select_task_for_ui,
        inputs=[task_selector, tasks_state],
        outputs=outputs,
    )
    run_it_now.click(
        fn=run_task_now,
        inputs=[task_root, task_json],
        outputs=[chatbot, tasks_state, selected_task_state, task_selector, task_summary, task_json],
    )

def run_task_now(task_root, task_json):
    # build a sub-agent
    session_id = str(uuid.uuid4())
    provider = os.environ.get("LLM_PROVIDER", "bedrock").lower()
    if provider not in _provider_map:
        raise ValueError(f"Unknown LLM_PROVIDER '{provider}'. Choose from: {list(_provider_map)}")
    cfg_path, factory, cfg_key = _provider_map[provider]
    llm = factory(cfg_path)
    with open("config/agent.yaml", "r", encoding="utf-8") as handle:
        agent_cfg = yaml.safe_load(handle) or {}
        tool_choices = agent_cfg.get("tool_choices", [])
    memory = RagMemoryStore(s3_path=agent_cfg.get("s3_memory_path"), force_sync=False)
    agent = AutoAgent(
        llm=llm,
        memory=memory, 
        user_id=agent_cfg.get("user_id", "admin"), 
        session_id=session_id,
        max_tool_rounds=agent_cfg.get("max_tool_rounds", 100000)
    )
    for chat_history, _ in agent.gradio_chat_stream(
        user_image=None,
        user_text=f"Finish this task: {task_json["_source_file"] }",
        history=[],
        enabled_tools=tool_choices
    ):
        yield [agent.to_gradio_messages(chat_history)] + _reload_tasks_for_ui(task_root)
    