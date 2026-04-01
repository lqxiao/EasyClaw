from agent import AutoAgent
from memory import RagMemoryStore
from apis import BedrockAPI, AnthropicAPI, OpenAIAPI
from apis import call_qwen_image_edition, to_base64
from skills_browser import load_skill_preview, open_folder
from task import TASK_UI_CSS, build_task_tab
import gradio as gr
import os
import uuid
import yaml
from PIL import Image as PILImage

ui_css = """
:root {
  --chat-tab-offset: 56px;
  --chat-max-width: 1100px;
}
.gradio-container {
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
}
html, body, .gradio-container {
  height: 100%;
  min-height: 100dvh;
}
body {
  margin: 0;
}
#chat-tab {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-height: calc(100dvh - var(--chat-tab-offset));
}
#chat-shell {
  width: min(100%, var(--chat-max-width));
  margin: 0 auto;
  padding: 0 16px 20px;
  flex: 1 1 auto;
  height: calc(100dvh - var(--chat-tab-offset) - 24px);
  min-height: 0;
  display: flex;
  flex-direction: column;
}
#chat-main {
  width: 100%;
  min-height: 0;
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  padding-bottom: 0px;
}
#chatbot {
  flex: 1 1 auto;
  min-height: 320px;
  height: 110%;
}
#workspace-explorer {
  flex: 1 1 auto;
  min-height: 0;
  height: 100%;
}
#skills-layout {
  min-height: calc(100dvh - var(--chat-tab-offset) - 24px);
}
#skills-tree,
#skills-preview {
  min-height: 0;
}
#chat-composer {
  width: 100%;
  margin-top: auto;
  position: sticky;
  bottom: -12px;
  z-index: 10;
  padding: 0px 0px 0px;
  background: var(--body-background-fill, white);
}
#chat-input-row {
  gap: 8px;
  align-items: flex-end;
}
#chat-input-row > div {
  min-width: 0;
}
#chat-input-row .gr-textbox {
  flex: 1 1 auto;
}
#send-button {
  align-self: flex-end;
}
@media (max-width: 768px) {
  #chat-shell {
    height: calc(100dvh - var(--chat-tab-offset) - 20px);
    padding: 0 12px 16px;
  }
  #chat-composer {
    padding: 10px 12px calc(14px + env(safe-area-inset-bottom));
  }
  #chat-input-row {
    flex-direction: column;
    align-items: stretch;
  }
  #send-button {
    align-self: stretch;
  }
}
""" + TASK_UI_CSS


def _open_workspace():
        base = os.path.join(os.getcwd(), "workspace")
        try:
            return open_folder(base)
        except Exception as exc:
            return f"Failed to open Finder: {exc}"


def _extract_multimodal_input(payload):
        if not isinstance(payload, dict):
            return "", None
        text = str(payload.get("text", "") or "")
        files = payload.get("files") or []
        if not isinstance(files, list) or not files:
            return text, None
        first_file = files[0]
        if not isinstance(first_file, str) or not first_file:
            return text, None
        try:
            with PILImage.open(first_file) as img:
                return text, img.copy()
        except Exception:
            return text, None

if __name__ == "__main__":
    session_id = str(uuid.uuid4())
    user_id = "admin"
    s3_memory_path = "s3://shopqa-users/liqiangx/tmp/memory_database"  # set to an S3 path like "s3://bucket/path" to use S3 storage
    tool_choices = [
        "exec",
        "memory_profile",
        "memory_history_retrieve",
        "fetch_image",
    ]

    _provider_map = {
        "bedrock":    ("config/bedrock_claude.yaml",   BedrockAPI.from_yaml,   "bedrock"),
        "anthropic":  ("config/anthropic_claude.yaml", AnthropicAPI.from_yaml, "anthropic"),
        "openai":     ("config/openai.yaml",           OpenAIAPI.from_yaml,    "openai"),
    }
    provider = os.environ.get("LLM_PROVIDER", "bedrock").lower()
    if provider not in _provider_map:
        raise ValueError(f"Unknown LLM_PROVIDER '{provider}'. Choose from: {list(_provider_map)}")
    cfg_path, factory, cfg_key = _provider_map[provider]
    llm = factory(cfg_path)
    cfg = {}
    try:
        with open(cfg_path, "r", encoding="utf-8") as handle:
            cfg = yaml.safe_load(handle) or {}
    except FileNotFoundError:
        cfg = {}
    agent_cfg = cfg.get("agent", {}) if isinstance(cfg, dict) else {}
    max_tool_rounds = int(agent_cfg.get("max_tool_rounds", 20))
    memory = RagMemoryStore(s3_path=s3_memory_path, force_sync=False)
    agent = AutoAgent(
        llm=llm,
        memory=memory, 
        user_id=user_id, 
        session_id=session_id,
        max_tool_rounds=max_tool_rounds)

    with gr.Blocks(title="Cute AI Chat", fill_height=True) as demo:
        workspace_root = os.path.join(os.getcwd(), "workspace")
        with gr.Tabs():
            with gr.Tab("Chat", elem_id="chat-tab", scale=1):
                with gr.Sidebar(open=False):
                    gr.Markdown(
                        "## Tools\nChoose which tools the agent can use in this chat."
                    )
                    enabled_tools = gr.CheckboxGroup(
                        choices=tool_choices,
                        value=tool_choices,
                        label="Enabled tools",
                    )
                with gr.Column(elem_id="chat-shell", scale=1, min_width=0):
                    with gr.Column(elem_id="chat-main", scale=1, min_width=0):
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
                        claude_state = gr.State([])
                        pending_text = gr.State("")
                        pending_image = gr.State(None)
                    with gr.Column(elem_id="chat-composer"):
                        with gr.Row(elem_id="chat-input-row"):
                            msg = gr.MultimodalTextbox(
                                show_label=False,
                                placeholder="Ask something...",
                                lines=3,
                                max_lines=6,
                                sources=["upload"],
                                file_types=["image"],
                                file_count="single",
                                submit_btn=True,
                                stop_btn=True,
                                scale=4,
                                container=False,
                            )
            with gr.Tab("Workspace", scale=1):
                gr.Markdown("## Workspace")
                workspace_explorer = gr.FileExplorer(
                    root_dir=workspace_root,
                    label="workspace/",
                    container=False,
                    elem_id="workspace-explorer",
                    scale=1,
                    height="100%",
                )
                open_finder = gr.Button("Open in Finder")
                open_finder.click(_open_workspace, None, None)
            with gr.Tab("Skills"):
                skills_root = os.path.join(workspace_root, "SKILLS")
                gr.Markdown("## Skills")
                with gr.Row(elem_id="skills-layout"):
                    with gr.Column(scale=1, min_width=280, elem_id="skills-tree"):
                        skills_explorer = gr.FileExplorer(
                            root_dir=skills_root,
                            glob="**/*",
                            file_count="single",
                            label="SKILLS/",
                            elem_id="skills-explorer",
                            height=640,
                        )
                        open_skills = gr.Button("Open SKILLS in Finder")
                    with gr.Column(scale=2, min_width=420, elem_id="skills-preview"):
                        skills_preview_header = gr.Markdown(
                            "## Skills Preview\nSelect a file or folder from `SKILLS/`."
                        )
                        skills_preview_code = gr.Code(
                            value="",
                            language="markdown",
                            label="Preview",
                            lines=28,
                            max_lines=36,
                            interactive=False,
                        )
                skills_explorer.change(
                    fn=lambda selected: load_skill_preview(selected, skills_root),
                    inputs=skills_explorer,
                    outputs=[skills_preview_header, skills_preview_code],
                )
                open_skills.click(lambda: open_folder(skills_root), None, None)
            with gr.Tab("Tasks", elem_id="task-tab", scale=1):
                build_task_tab(os.path.join(workspace_root, "TASKS"))

        def _preview_user_message(user_payload, claude_messages):
            user_text, user_image = _extract_multimodal_input(user_payload)
            if not (user_text and user_text.strip()) and user_image is None:
                return (
                    agent.to_gradio_messages(claude_messages),
                    claude_messages,
                    None,
                    "",
                    None,
                )
            user_message = agent.construct_message(user_text=user_text, user_image=user_image)
            claude_messages.append(user_message)
            return (
                agent.to_gradio_messages(claude_messages),
                claude_messages,
                None,
                user_text,
                user_image,
            )

        def _gradio_handler(user_text, user_image, claude_messages, enabled_tool_names):
            if not (user_text and user_text.strip()) and user_image is None:
                yield (
                    agent.to_gradio_messages(claude_messages),
                    claude_messages,
                    None,
                    "",
                    None,
                )
                return
            try:
                for current_history, _ in agent.gradio_chat_stream(
                    user_text=user_text,
                    user_image=user_image,
                    history=claude_messages,
                    append_user=False,
                    enabled_tools=enabled_tool_names or [],
                ):
                    yield (
                        agent.to_gradio_messages(current_history),
                        current_history,
                        None,
                        "",
                        None,
                    )
            except RuntimeError:
                claude_messages, _ = agent.gradio_chat(
                    user_text=user_text,
                    user_image=user_image,
                    history=claude_messages,
                    append_user=False,
                    enabled_tools=enabled_tool_names or [],
                )
                yield (
                    agent.to_gradio_messages(claude_messages),
                    claude_messages,
                    None,
                    "",
                    None,
                )

        submit_preview_event = msg.submit(
            _preview_user_message,
            [msg, claude_state],
            [chatbot, claude_state, msg, pending_text, pending_image],
        )
        submit_response_event = submit_preview_event.then(
            _gradio_handler,
            [pending_text, pending_image, claude_state, enabled_tools],
            [chatbot, claude_state, msg, pending_text, pending_image],
        )
        msg.stop(
            lambda: None,
            None,
            None,
            cancels=[submit_response_event],
            queue=False,
        )

    demo.queue()
    demo.launch(css=ui_css)
