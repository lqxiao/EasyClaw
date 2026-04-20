# Task: Summarize Slack Starred Chats

## Objective

Review the user's starred Slack chats in the Slack web app and produce a concise but useful summary of:
- what is happening across those starred conversations
- what the user needs to do next
- what is urgent, blocked, or easy to miss

## Context

This task is read-only.

The goal is not to archive messages or respond in Slack. The goal is to help the user quickly understand:
- current project status
- pending asks
- decisions waiting on them
- deadlines and follow-ups

The agent should focus on starred channels and starred direct messages because those are the highest-priority conversations for this task.

## Required Skills / Tools

- Required skill: `browser_use`
- Target application: Slack web app
- Browser mode: headed mode, so the user can log in if needed

## Workflow

1. Open Slack in the browser with the `browser_use` skill in headed mode.
2. If Slack requires login and the session is not already authenticated, stop and ask the user to log in.
3. Navigate to the user's starred chats, starred channels, and starred direct messages.
4. Open each starred conversation and read the recent important messages.
5. Focus on:
   - project status
   - blockers
   - requests directed at the user
   - deadlines
   - follow-ups
   - decisions already made
6. Ignore casual chatter unless it affects action items or priorities.
7. Track items that require user action, especially:
   - direct requests
   - questions awaiting reply
   - approvals
   - deadlines
   - blocked work needing escalation
8. If the same topic appears in multiple starred chats, merge it into one coherent summary instead of repeating it blindly.

## Output

Produce a structured summary with these sections:

### 1. Overall Summary
- A short high-level summary of what is happening across all starred Slack conversations.

### 2. By Channel / Chat
For each starred channel or direct message, include:
- channel or chat name
- what is happening
- important updates
- open questions
- urgency level

### 3. TODO For User
List the concrete things the user needs to do, including:
- replies they should send
- decisions they need to make
- approvals they need to give
- deadlines they should not miss

### 4. Risks / Missed Items
- anything urgent
- anything that looks blocked
- anything that may need escalation

## Constraints

- Do not send any Slack messages unless the user explicitly asks.
- Do not modify Slack content.
- Stay focused on reading and summarizing.
- Be concise but specific.
- If a starred chat cannot be accessed, mention it in the final summary instead of guessing.
- Do not invent action items that are not supported by the messages you read.

## Stop Conditions / Escalation

- Stop and ask the user to log in if Slack is not authenticated.
- Stop and ask the user if the workspace or account shown in Slack looks wrong.
- Stop and ask the user if Slack content is inaccessible because of permissions or an unexpected UI state.
- Do not continue if the task would require sending messages or taking any action in Slack.

## Success Criteria

The task is successful if the agent returns:
- a short overall summary
- a per-channel or per-chat summary of the starred conversations it could access
- a clear TODO list for the user
- a risk / urgent-items section
