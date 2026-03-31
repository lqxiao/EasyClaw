---
name: slack-api
description: Connects to Slack workspace via Bot Token to send messages, read channel history, manage channels/users, upload files, and perform interactive operations. Use when the user needs to interact with Slack — sending notifications, reading messages, posting rich alerts, or automating Slack workflows.
allowed-tools: Bash(slack-api:*), exec
---

# Slack API Skill

Interact with a Slack workspace using Bot Token + `slack_sdk`. Supports sending messages (plain, rich, Block Kit), reading channel history, listing channels/users, replying to threads, adding reactions, uploading files, and more.

## Prerequisites

1. **slack_sdk** must be installed:
   ```bash
   pip install slack_sdk
   ```

2. **Slack Bot Token** must be set as environment variable:
   ```bash
   export SLACK_BOT_TOKEN="xoxb-your-token-here"
   ```

3. **Bot must be invited** to target channels:
   In Slack, type `/invite @YourBotName` in the channel.

### How to get a Bot Token (first-time setup)

1. Go to https://api.slack.com/apps → **Create New App** → **From scratch**
2. Go to **OAuth & Permissions** → Add these **Bot Token Scopes**:
   - `chat:write` — Send messages
   - `chat:write.public` — Send to public channels without joining
   - `channels:history` — Read public channel history
   - `channels:read` — List channels
   - `groups:history` — Read private channel history
   - `im:history` — Read DM history
   - `users:read` — List users
   - `reactions:write` — Add emoji reactions
   - `files:write` — Upload files
3. Click **Install to Workspace** → Authorize
4. Copy the **Bot User OAuth Token** (`xoxb-...`)

## Core Workflow

1. **Verify**: Test connection and confirm bot is working
2. **Discover**: List channels and users to find target IDs
3. **Send**: Post messages (plain text, rich, or Block Kit)
4. **Read**: Retrieve channel message history
5. **Interact**: Reply to threads, add reactions, upload files

## Usage

All commands use the helper script at `workspace/SKILLS/slack_api/slack_helper.py`.

### Test Connection

```bash
python3 workspace/SKILLS/slack_api/slack_helper.py test
```
Returns bot name, team, and bot ID if successful.

### List Channels

```bash
python3 workspace/SKILLS/slack_api/slack_helper.py channels
python3 workspace/SKILLS/slack_api/slack_helper.py channels --limit 50
```

### Find Channel ID by Name

```bash
python3 workspace/SKILLS/slack_api/slack_helper.py find-channel general
python3 workspace/SKILLS/slack_api/slack_helper.py find-channel "my-channel"
```

### Send Plain Text Message

```bash
python3 workspace/SKILLS/slack_api/slack_helper.py send "#general" "Hello World!"
python3 workspace/SKILLS/slack_api/slack_helper.py send "C01XXXXXXXX" "Hello by channel ID"
```

### Send Rich Message (with color, fields)

```bash
python3 workspace/SKILLS/slack_api/slack_helper.py send-rich "#general" "Report Title" \
    --fields '{"Status": "OK", "VIX": "30.61", "S&P": "6343.72"}' \
    --color "#ff0000"
```

### Send Block Kit Message

```bash
python3 workspace/SKILLS/slack_api/slack_helper.py send-blocks "#general" \
    --blocks '[{"type":"section","text":{"type":"mrkdwn","text":"*Hello* from Block Kit"}}]' \
    --text "Hello from Block Kit"
```

### Send Market Alert (built-in template)

```bash
python3 workspace/SKILLS/slack_api/slack_helper.py market-alert "#trading" \
    --sp500 6343.72 --vix 30.61 --oil 102.98
```

### Read Channel Messages

```bash
python3 workspace/SKILLS/slack_api/slack_helper.py read "#general"
python3 workspace/SKILLS/slack_api/slack_helper.py read "#general" --limit 20
python3 workspace/SKILLS/slack_api/slack_helper.py read "C01XXXXXXXX" --hours 24
```

### Reply to Thread

```bash
python3 workspace/SKILLS/slack_api/slack_helper.py reply "#general" "1711234567.000100" "Got it!"
```
The second argument is the thread timestamp (`ts`) from a previous message.

### Add Emoji Reaction

```bash
python3 workspace/SKILLS/slack_api/slack_helper.py react "#general" "1711234567.000100" "thumbsup"
python3 workspace/SKILLS/slack_api/slack_helper.py react "C01XXX" "1711234567.000100" "rocket"
```

### List Users

```bash
python3 workspace/SKILLS/slack_api/slack_helper.py users
```

### Upload File

```bash
python3 workspace/SKILLS/slack_api/slack_helper.py upload "#general" "./report.pdf"
python3 workspace/SKILLS/slack_api/slack_helper.py upload "#general" "./chart.png" --title "Daily Chart"
```

### Update a Message

```bash
python3 workspace/SKILLS/slack_api/slack_helper.py update "C01XXXXXXXX" "1711234567.000100" "Updated text"
```

### Delete a Message

```bash
python3 workspace/SKILLS/slack_api/slack_helper.py delete "C01XXXXXXXX" "1711234567.000100"
```

## Common Patterns

### Send a formatted report to a channel

```bash
# 1. Find the channel
python3 workspace/SKILLS/slack_api/slack_helper.py find-channel "trading-alerts"

# 2. Send a rich message
python3 workspace/SKILLS/slack_api/slack_helper.py send-rich "C01XXXXXXXX" "📊 Daily Report" \
    --fields '{"S&P 500": "6,343.72 (-2.3%)", "VIX": "30.61", "Oil": "$102.98", "Risk": "🔴 High"}' \
    --color "#ff0000"
```

### Monitor a channel and respond

```bash
# 1. Read recent messages
python3 workspace/SKILLS/slack_api/slack_helper.py read "#support" --limit 5

# 2. Reply to a specific thread
python3 workspace/SKILLS/slack_api/slack_helper.py reply "#support" "1711234567.000100" "Looking into this now"

# 3. React to acknowledge
python3 workspace/SKILLS/slack_api/slack_helper.py react "#support" "1711234567.000100" "eyes"
```

### Inline Python usage (advanced)

```python
import sys
sys.path.insert(0, "workspace/SKILLS/slack_api")
from slack_helper import SlackBot

bot = SlackBot()  # reads SLACK_BOT_TOKEN from env
bot.test_connection()
bot.send_message("#general", "Hello from Python!")
messages = bot.read_messages("#general", limit=5)
```

## Tips

1. **Channel can be name or ID** — `#general` or `C01XXXXXXXX` both work
2. **Always test connection first** — `python3 slack_helper.py test`
3. **Bot must be in the channel** — `/invite @BotName` in Slack
4. **Rate limits** — Slack allows ~1 msg/sec/channel; the helper adds delays for bulk operations
5. **Token security** — Never hardcode tokens; always use `SLACK_BOT_TOKEN` env var
6. **Thread ts** — Get the `ts` value from send/read commands to reply to threads
7. **JSON output** — Add `--json` flag to any command for machine-readable output

## Troubleshooting

| Error | Fix |
|-------|-----|
| `not_in_channel` | Invite bot: `/invite @BotName` |
| `channel_not_found` | Check channel name/ID; use `channels` command to list |
| `missing_scope` | Add scope in Slack App settings → reinstall app |
| `invalid_auth` | Check `SLACK_BOT_TOKEN` is set correctly |
| `ratelimited` | Slow down; add `time.sleep(1)` between calls |

## Token Types Reference

| Token | Prefix | Purpose |
|-------|--------|---------|
| Bot Token | `xoxb-` | Bot operations (this skill uses this) |
| User Token | `xoxp-` | Act as user |
| App-Level Token | `xapp-` | Socket Mode / Events API |
| Webhook URL | `https://hooks.slack.com/...` | One-way message posting only |
