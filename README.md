# EasyClaw

EasyClaw is a more user-friendly open-source agent system inspired by OpenClaw, built for everyday task automation and non-technical users.

It launches a local Gradio web UI where you can chat with the agent, browse the `workspace/` folder, and inspect enabled skills.

# Quick Start 
## For Non-Tech 
1. Download this repo to your computer.
2. Open Terminal.
3. Anthorize the APP
```bash 
xattr -cr /path/to/EASYCLAW 
chmod +x /path/to/EASYCLAW
```
4. Double-Click EASYCLAW/dist/EASYCLAW icon. 
5. Once APP opened, chose your API provider in navbar and input key.

## For Developer
### Requirements

- Python 3.10 or newer
- Credentials for your chosen provider (see table above)
- [Optional] Access to an S3 bucket for cloud-backed memory storage — defaults to local at `~/.cache/cute_ai/memory/`

### Install

1. Open a terminal in this project folder:

```bash
cd /Path/to/EasyClaw
```

2. Install `uv` (recommended — pip's resolver cannot handle this project's dependency graph):

```bash
pip install uv
```

3. Create and activate a virtual environment:

```bash
uv venv .venv
source .venv/bin/activate
```

4. Install pinned dependencies:

```bash
uv pip sync requirements.lock
```

5. Set credentials for your chosen provider:

**Bedrock:**
```bash
aws configure
# or
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=us-east-1
```

**Anthropic:**
```bash
export ANTHROPIC_API_KEY=your_key
```

**OpenAI:**
```bash
export OPENAI_API_KEY=your_key
```

### Configure

Each provider has its own config file under `config/`:

- `config/bedrock_claude.yaml` — Bedrock region, model ID, timeouts
- `config/anthropic_claude.yaml` — Anthropic model ID, max tokens
- `config/openai.yaml` — OpenAI model ID, max tokens, and model-specific flags (e.g. `disable_temperature: true` for models that don't support it)

Memory storage defaults to local (`~/.cache/cute_ai/memory/memory.db`). To use S3, set `s3_memory_path` in `main.py` to your S3 path (e.g. `s3://my-bucket/memory`) — the agent will sync to S3 on exit.

### Open The App

```bash
python main.py
```

Gradio will print a local URL in the terminal. Open that URL in your browser. It is usually:

```text
http://127.0.0.1:7860
```

### What You Should See

- `Chat` tab for talking to the agent
- `Workspace` tab for browsing files under `workspace/`
- `Skills` tab for previewing skill files
- `Tasks` tab for viewing and managing agent tasks

### Supported LLM Providers

EasyClaw supports three providers out of the box. Pick the one you have access to:

| Provider | Config file | Env var needed |
|----------|-------------|----------------|
| Amazon Bedrock (default) | `config/bedrock_claude.yaml` | AWS credentials |
| Anthropic direct API | `config/anthropic_claude.yaml` | `ANTHROPIC_API_KEY` |
| OpenAI | `config/openai.yaml` | `OPENAI_API_KEY` |

Select a provider by setting `LLM_PROVIDER` before running:

```bash
LLM_PROVIDER=anthropic python main.py   # Anthropic direct
LLM_PROVIDER=openai python main.py      # OpenAI
python main.py                          # defaults to Bedrock
```

Each config file lets you set `model_id`, `max_tokens`, `temperature`, and `agent.max_tool_rounds`.


## Troubleshooting

- Use `uv pip sync requirements.lock` instead of `pip install` — plain pip cannot resolve this project's dependencies.
- If the app fails on startup with credential errors, verify your provider's API key or AWS region.
- If the browser page does not open, copy the Gradio URL from the terminal and paste it into your browser manually.
