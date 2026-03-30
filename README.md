# EasyClaw

EasyClaw is a more user-friendly open-source agent system inspired by OpenClaw, built for everyday task automation and non-technical users.

It launches a local Gradio web UI where you can chat with the agent, browse the `workspace/` folder, and inspect enabled skills.

## Requirements

- Python 3.10 or newer
- AWS credentials configured locally
- Access to Amazon Bedrock for the model in [`config/bedrock_claude.yaml`]
- [Optional] Access to the S3 bucket/path used by the memory store in [`main.py`]

## Install

1. Open a terminal in this project folder:

```bash
cd /Path/to/EasyClaw
```

2. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. [To be expaneded to other sources] Make sure AWS credentials are available in your shell. For example, you can use:

```bash
aws configure
```

or export credentials manually before launching the app:

```bash
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=us-east-1
```

## Configure

- Bedrock model settings live in [`config/bedrock_claude.yaml`] 
- The main app currently uses an S3-backed memory database path defined in [`main.py`]. If you want to use a different bucket or switch to local storage, update that file before starting the app.

## Open The App

Start the main UI with:

```bash
python main.py
```

Gradio will print a local URL in the terminal. Open that URL in your browser. It is usually:

```text
http://127.0.0.1:7860
```

## What You Should See

- `Chat` tab for talking to the agent
- `Workspace` tab for browsing files under `workspace/`
- `Skills` tab for previewing skill files

## Troubleshooting

- If `pip install` fails, confirm the virtual environment is activated and that you are using a recent Python version.
- If the app fails on startup with AWS errors, verify your Bedrock access, AWS region, and S3 permissions.
- If the browser page does not open, copy the Gradio URL from the terminal and paste it into your browser manually.
