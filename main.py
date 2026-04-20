from agent import AutoAgent
from memory import RagMemoryStore
from apis import _provider_map
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

def _create_llm(provider: str, api_key: str = "", model: str = ""):
    """Create an LLM instance for the given provider, with optional API key and model override."""
    provider = provider.lower()
    if provider not in _provider_map:
        raise ValueError(f"Unknown provider '{provider}'. Choose from: {list(_provider_map)}")
    cfg_path, factory, cfg_key = _provider_map[provider]
    if provider == "anthropic" and api_key.strip():
        from apis import AnthropicAPI
        cfg = yaml.safe_load(open(cfg_path, encoding="utf-8")) or {}
        a = cfg.get("anthropic", {})
        return AnthropicAPI(
            api_key=api_key.strip(),
            model_id=model.strip() or a.get("model_id", "claude-sonnet-4-6"),
            max_tokens=int(a.get("max_tokens", 128000)),
            temperature=float(a.get("temperature", 0.5)),
        )
    elif provider == "openai" and api_key.strip():
        from apis import OpenAIAPI
        cfg = yaml.safe_load(open(cfg_path, encoding="utf-8")) or {}
        o = cfg.get("openai", {})
        return OpenAIAPI(
            api_key=api_key.strip(),
            model_id=model.strip() or o.get("model_id", "gpt-4o"),
            max_tokens=int(o.get("max_tokens", 128000)),
            temperature=float(o.get("temperature", 0.5)),
            disable_temperature=bool(o.get("disable_temperature", False)),
        )
    elif provider == "codex" and api_key.strip():
        from apis import CodexAPI
        return CodexAPI(
            api_key=api_key.strip(),
            model_id=model.strip() or "codex-mini-latest",
            max_tokens=128000,
        )
    return factory(cfg_path)


def _safe_create_llm(provider, api_key="", model=""):
    """Try to create LLM; return (llm, None) on success or (None, error_msg) on failure."""
    try:
        llm = _create_llm(provider, api_key, model)
        # For bedrock, do a lightweight credential check so we fail fast
        if provider == "bedrock":
            import boto3
            sts = boto3.client("sts")
            sts.get_caller_identity()
        return llm, None
    except Exception as e:
        return None, str(e)


def _safe_create_memory(agent_cfg):
    """Try to create memory store; fall back to local-only on credential errors."""
    s3_path = agent_cfg.get("s3_memory_path")
    if s3_path:
        try:
            return RagMemoryStore(s3_path=s3_path, force_sync=False)
        except Exception as e:
            print(f"[WARN] S3 memory unavailable ({e}), falling back to local-only memory.")
    return RagMemoryStore(s3_path=None, force_sync=False)


# Mutable state container so closures can update it
class _AppState:
    llm_ready = False

_state = _AppState()


if __name__ == "__main__":
    session_id = str(uuid.uuid4())
    initial_provider = os.environ.get("LLM_PROVIDER", "bedrock").lower()
    if initial_provider not in _provider_map:
        initial_provider = "bedrock"

    # --- Safe LLM init: don't crash if credentials are missing ---
    llm, llm_error = _safe_create_llm(initial_provider)
    _state.llm_ready = llm is not None

    with open("config/agent.yaml", "r", encoding="utf-8") as handle:
        agent_cfg = yaml.safe_load(handle) or {}
        tool_choices = agent_cfg.get("tool_choices", [])
    max_tool_rounds = int(agent_cfg.get("max_tool_rounds", 20))

    # --- Safe memory init: fall back to local if S3 creds missing ---
    memory = _safe_create_memory(agent_cfg)

    agent = AutoAgent(
        llm=llm,
        memory=memory,
        user_id=agent_cfg.get("user_id", "admin"),
        session_id=session_id,
        max_tool_rounds=agent_cfg.get("max_tool_rounds", 100000)
    )
    with gr.Blocks(title="Cute AI Chat", fill_height=True) as demo:
        workspace_root = os.path.join(os.getcwd(), "workspace")
        with gr.Tabs():
            with gr.Tab("Chat", elem_id="chat-tab", scale=1):
                with gr.Sidebar(open=not _state.llm_ready):
                    gr.Markdown("## LLM Provider")
                    _provider_models = {
                        "bedrock": [],
                        "anthropic": ["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5"],
                        "openai": ["gpt-4o", "gpt-4o-mini", "o3-mini"],
                        "codex": ["codex-mini-latest", "gpt-4o", "o3-mini"],
                    }
                    provider_dropdown = gr.Dropdown(
                        choices=["bedrock", "anthropic", "openai", "codex"],
                        value=initial_provider,
                        label="Provider",
                    )
                    model_dropdown = gr.Dropdown(
                        choices=_provider_models.get(initial_provider, []),
                        value="",
                        label="Model (optional override)",
                        allow_custom_value=True,
                        visible=initial_provider != "bedrock",
                    )
                    api_key_input = gr.Textbox(
                        label="API Key",
                        placeholder="sk-... (leave empty for Bedrock/env var)",
                        type="password",
                        visible=initial_provider in ("anthropic", "openai", "codex"),
                    )
                    _key_links = {
                        "codex": "https://platform.openai.com/api-keys",
                        "openai": "https://platform.openai.com/api-keys",
                        "anthropic": "https://console.anthropic.com/settings/keys",
                    }
                    api_key_link = gr.Markdown(
                        value=f"[Get API key]({_key_links.get(initial_provider, '')})"
                              if initial_provider in _key_links else "",
                        visible=initial_provider in _key_links,
                    )
                    if _state.llm_ready:
                        _initial_status = f"✅ Using **{initial_provider}**"
                    else:
                        _initial_status = (
                            f"⚠️ **No credentials found for {initial_provider}.**\n\n"
                            f"Please select a provider and enter your API key to get started.\n\n"
                            f"_Error: {llm_error}_"
                        )
                    provider_status = gr.Markdown(value=_initial_status)

                    def _on_provider_change(new_provider, model, api_key):
                        needs_key = new_provider in ("anthropic", "openai", "codex")
                        link_url = _key_links.get(new_provider, "")
                        link_md = f"[Get API key]({link_url})" if link_url else ""
                        models = _provider_models.get(new_provider, [])
                        try:
                            new_llm = _create_llm(new_provider, api_key, model)
                            # For bedrock, verify credentials
                            if new_provider == "bedrock":
                                import boto3
                                sts = boto3.client("sts")
                                sts.get_caller_identity()
                            agent.llm = new_llm
                            _state.llm_ready = True
                            model_name = getattr(new_llm, "model_id", new_provider)
                            return (
                                gr.update(choices=models, value=model if model in models else "", visible=new_provider != "bedrock"),
                                gr.update(visible=needs_key),
                                gr.update(value=link_md, visible=bool(link_url)),
                                f"✅ Using **{new_provider}** / `{model_name}`",
                            )
                        except Exception as e:
                            _state.llm_ready = False
                            return (
                                gr.update(choices=models, visible=new_provider != "bedrock"),
                                gr.update(visible=needs_key),
                                gr.update(value=link_md, visible=bool(link_url)),
                                f"⚠️ **Error:** {e}",
                            )

                    provider_dropdown.change(
                        _on_provider_change,
                        [provider_dropdown, model_dropdown, api_key_input],
                        [model_dropdown, api_key_input, api_key_link, provider_status],
                    )
                    model_dropdown.change(
                        _on_provider_change,
                        [provider_dropdown, model_dropdown, api_key_input],
                        [model_dropdown, api_key_input, api_key_link, provider_status],
                    )
                    api_key_input.change(
                        _on_provider_change,
                        [provider_dropdown, model_dropdown, api_key_input],
                        [model_dropdown, api_key_input, api_key_link, provider_status],
                    )

                    gr.Markdown("---\n## Tools")
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
                            container=False,
                            group_consecutive_messages=True,
                            autoscroll=False,
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
                                max_plain_text_length=20000,
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

            # --- Guard: check if LLM is configured ---
            if agent.llm is None:
                error_msg = {
                    "role": "assistant",
                    "content": [{"type": "text", "text":
                        "⚠️ **No LLM provider configured yet.**\n\n"
                        "Please open the **sidebar** (click the ☰ icon) and:\n"
                        "1. Select a **Provider** (e.g. `anthropic` or `openai`)\n"
                        "2. Enter your **API Key**\n"
                        "3. Try sending your message again.\n\n"
                        "_Tip: You can get an Anthropic key at "
                        "[console.anthropic.com](https://console.anthropic.com/settings/keys) "
                        "or an OpenAI key at "
                        "[platform.openai.com](https://platform.openai.com/api-keys)._"
                    }],
                }
                claude_messages.append(error_msg)
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
            except RuntimeError as e:
                error_str = str(e)
                # Check if this is a credential/auth error
                cred_keywords = ["credential", "nocredential", "expired",
                                 "authenticate", "401", "403", "mwinit",
                                 "sso login", "token", "unauthorized"]
                if any(kw in error_str.lower() for kw in cred_keywords):
                    error_msg = {
                        "role": "assistant",
                        "content": [{"type": "text", "text":
                            f"⚠️ **Authentication error:**\n\n`{error_str}`\n\n"
                            "Please open the **sidebar** and reconfigure your "
                            "LLM provider or enter a valid API key."
                        }],
                    }
                    claude_messages.append(error_msg)
                    yield (
                        agent.to_gradio_messages(claude_messages),
                        claude_messages,
                        None,
                        "",
                        None,
                    )
                    return
                # Non-streaming fallback for other RuntimeErrors
                try:
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
                except Exception as e2:
                    error_msg = {
                        "role": "assistant",
                        "content": [{"type": "text", "text":
                            f"⚠️ **Error:** {e2}"
                        }],
                    }
                    claude_messages.append(error_msg)
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
