#!/usr/bin/env python3
"""
Slack API Helper — CLI + importable module
Usage:
    python3 slack_helper.py <command> [args] [options]

Commands:
    test                                  Test connection
    channels [--limit N]                  List channels
    find-channel <name>                   Find channel ID by name
    send <channel> <text>                 Send plain text message
    send-rich <channel> <title> --fields JSON [--color HEX]
    send-blocks <channel> --blocks JSON [--text TEXT]
    market-alert <channel> --sp500 N --vix N --oil N
    read <channel> [--limit N] [--hours N]
    reply <channel> <thread_ts> <text>    Reply to thread
    react <channel> <ts> <emoji>          Add emoji reaction
    users                                 List users
    upload <channel> <filepath> [--title T]
    update <channel> <ts> <new_text>      Update message
    delete <channel> <ts>                 Delete message

Environment:
    SLACK_BOT_TOKEN    Bot User OAuth Token (xoxb-...)
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta

try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
except ImportError:
    print("❌ slack_sdk not installed. Run: pip install slack_sdk")
    sys.exit(1)


# ============================================
# SlackBot Class (importable)
# ============================================

class SlackBot:
    """Slack Bot wrapper for common operations."""

    def __init__(self, token=None):
        self.token = token or os.environ.get("SLACK_BOT_TOKEN")
        if not self.token:
            raise ValueError(
                "❌ No token. Set SLACK_BOT_TOKEN env var or pass token= argument.\n"
                "   export SLACK_BOT_TOKEN='xoxb-your-token'"
            )
        self.client = WebClient(token=self.token)
        self._user_cache = {}

    # --- Connection ---

    def test_connection(self):
        """Test bot connection. Returns dict with bot info."""
        try:
            resp = self.client.auth_test()
            info = {
                "ok": True,
                "bot_name": resp["user"],
                "team": resp["team"],
                "bot_id": resp["user_id"],
                "url": resp["url"],
            }
            return info
        except SlackApiError as e:
            return {"ok": False, "error": e.response["error"]}

    # --- Channels ---

    def list_channels(self, limit=20):
        """List public channels. Returns list of channel dicts."""
        try:
            resp = self.client.conversations_list(types="public_channel", limit=limit)
            return resp["channels"]
        except SlackApiError as e:
            return {"error": e.response["error"]}

    def find_channel_id(self, channel_name):
        """Find channel ID by name. Returns channel ID string or None."""
        channel_name = channel_name.lstrip("#")
        try:
            cursor = None
            while True:
                resp = self.client.conversations_list(
                    types="public_channel,private_channel", limit=200, cursor=cursor
                )
                for ch in resp["channels"]:
                    if ch["name"] == channel_name:
                        return ch["id"]
                cursor = resp.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break
            return None
        except SlackApiError as e:
            return None

    def _resolve_channel(self, channel):
        """Resolve channel name to ID if needed."""
        if channel.startswith("#"):
            return self.find_channel_id(channel)
        if not channel.startswith(("C", "D", "G")):
            return self.find_channel_id(channel)
        return channel

    # --- Send Messages ---

    def send_message(self, channel, text):
        """Send plain text message. Returns response dict."""
        try:
            resp = self.client.chat_postMessage(channel=channel, text=text)
            return {"ok": True, "ts": resp["ts"], "channel": resp["channel"]}
        except SlackApiError as e:
            return {"ok": False, "error": e.response["error"]}

    def send_rich_message(self, channel, title, fields, color="#36a64f"):
        """Send message with colored attachment and fields."""
        attachments = [
            {
                "color": color,
                "title": title,
                "fields": [
                    {"title": k, "value": str(v), "short": True}
                    for k, v in fields.items()
                ],
                "footer": f"SlackBot | {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            }
        ]
        try:
            resp = self.client.chat_postMessage(
                channel=channel, text=title, attachments=attachments
            )
            return {"ok": True, "ts": resp["ts"], "channel": resp["channel"]}
        except SlackApiError as e:
            return {"ok": False, "error": e.response["error"]}

    def send_blocks_message(self, channel, blocks, text="New message"):
        """Send Block Kit message."""
        try:
            resp = self.client.chat_postMessage(
                channel=channel, blocks=blocks, text=text
            )
            return {"ok": True, "ts": resp["ts"], "channel": resp["channel"]}
        except SlackApiError as e:
            return {"ok": False, "error": e.response["error"]}

    def send_market_alert(self, channel, sp500, vix, oil):
        """Send formatted market alert using Block Kit."""
        color = "🔴 High" if vix > 30 else "🟡 Medium" if vix > 20 else "🟢 Low"
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "📊 Market Alert", "emoji": True},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*S&P 500:*\n{sp500:,.2f}"},
                    {"type": "mrkdwn", "text": f"*VIX:*\n{vix:.2f}"},
                    {"type": "mrkdwn", "text": f"*Crude Oil:*\n${oil:.2f}"},
                    {"type": "mrkdwn", "text": f"*Risk Level:*\n{color}"},
                ],
            },
            {"type": "divider"},
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    }
                ],
            },
        ]
        return self.send_blocks_message(channel, blocks, text="Market Alert")

    # --- Read Messages ---

    def read_messages(self, channel, limit=10, hours=None):
        """Read channel message history. Returns list of message dicts."""
        channel_id = self._resolve_channel(channel)
        if not channel_id:
            return {"error": f"Channel not found: {channel}"}
        kwargs = {"channel": channel_id, "limit": limit}
        if hours:
            kwargs["oldest"] = str((datetime.now() - timedelta(hours=hours)).timestamp())
        try:
            resp = self.client.conversations_history(**kwargs)
            messages = resp["messages"]
            # Enrich with usernames
            for msg in messages:
                user_id = msg.get("user")
                if user_id:
                    msg["username"] = self._get_username(user_id)
            return messages
        except SlackApiError as e:
            return {"error": e.response["error"]}

    # --- Interactions ---

    def reply_to_thread(self, channel, thread_ts, text):
        """Reply to a message thread."""
        try:
            resp = self.client.chat_postMessage(
                channel=channel, thread_ts=thread_ts, text=text
            )
            return {"ok": True, "ts": resp["ts"]}
        except SlackApiError as e:
            return {"ok": False, "error": e.response["error"]}

    def add_reaction(self, channel, timestamp, emoji="thumbsup"):
        """Add emoji reaction to a message."""
        channel_id = self._resolve_channel(channel)
        if not channel_id:
            return {"ok": False, "error": f"Channel not found: {channel}"}
        try:
            self.client.reactions_add(
                channel=channel_id, timestamp=timestamp, name=emoji
            )
            return {"ok": True}
        except SlackApiError as e:
            return {"ok": False, "error": e.response["error"]}

    def upload_file(self, channel, filepath, title=None):
        """Upload a file to a channel."""
        try:
            resp = self.client.files_upload_v2(
                channel=channel,
                file=filepath,
                title=title or os.path.basename(filepath),
            )
            return {"ok": True, "file_id": resp.get("file", {}).get("id", "unknown")}
        except SlackApiError as e:
            return {"ok": False, "error": e.response["error"]}

    def update_message(self, channel, ts, new_text):
        """Update an existing message."""
        try:
            resp = self.client.chat_update(channel=channel, ts=ts, text=new_text)
            return {"ok": True, "ts": resp["ts"]}
        except SlackApiError as e:
            return {"ok": False, "error": e.response["error"]}

    def delete_message(self, channel, ts):
        """Delete a message."""
        try:
            self.client.chat_delete(channel=channel, ts=ts)
            return {"ok": True}
        except SlackApiError as e:
            return {"ok": False, "error": e.response["error"]}

    # --- Users ---

    def list_users(self):
        """List workspace users (non-bot)."""
        try:
            resp = self.client.users_list()
            users = [
                u
                for u in resp["members"]
                if not u["is_bot"] and u["id"] != "USLACKBOT" and not u.get("deleted")
            ]
            return users
        except SlackApiError as e:
            return {"error": e.response["error"]}

    def _get_username(self, user_id):
        """Get username with caching."""
        if user_id in self._user_cache:
            return self._user_cache[user_id]
        try:
            resp = self.client.users_info(user=user_id)
            name = resp["user"].get("real_name") or resp["user"]["name"]
            self._user_cache[user_id] = name
            return name
        except SlackApiError:
            return user_id


# ============================================
# CLI Interface
# ============================================

def _print_json(data):
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def _print_result(data, json_mode=False):
    if json_mode:
        _print_json(data)
    elif isinstance(data, dict) and "error" in data:
        print(f"❌ Error: {data['error']}")
    elif isinstance(data, dict) and data.get("ok"):
        for k, v in data.items():
            if k != "ok":
                print(f"  {k}: {v}")


def main():
    parser = argparse.ArgumentParser(description="Slack API Helper")
    parser.add_argument("--json", action="store_true", help="JSON output")
    sub = parser.add_subparsers(dest="command", help="Command")

    # test
    sub.add_parser("test", help="Test connection")

    # channels
    p = sub.add_parser("channels", help="List channels")
    p.add_argument("--limit", type=int, default=20)

    # find-channel
    p = sub.add_parser("find-channel", help="Find channel ID")
    p.add_argument("name", help="Channel name")

    # send
    p = sub.add_parser("send", help="Send message")
    p.add_argument("channel", help="Channel name or ID")
    p.add_argument("text", help="Message text")

    # send-rich
    p = sub.add_parser("send-rich", help="Send rich message")
    p.add_argument("channel")
    p.add_argument("title")
    p.add_argument("--fields", required=True, help="JSON dict of fields")
    p.add_argument("--color", default="#36a64f")

    # send-blocks
    p = sub.add_parser("send-blocks", help="Send Block Kit message")
    p.add_argument("channel")
    p.add_argument("--blocks", required=True, help="JSON array of blocks")
    p.add_argument("--text", default="New message")

    # market-alert
    p = sub.add_parser("market-alert", help="Send market alert")
    p.add_argument("channel")
    p.add_argument("--sp500", type=float, required=True)
    p.add_argument("--vix", type=float, required=True)
    p.add_argument("--oil", type=float, required=True)

    # read
    p = sub.add_parser("read", help="Read messages")
    p.add_argument("channel")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--hours", type=float, default=None)

    # reply
    p = sub.add_parser("reply", help="Reply to thread")
    p.add_argument("channel")
    p.add_argument("thread_ts")
    p.add_argument("text")

    # react
    p = sub.add_parser("react", help="Add reaction")
    p.add_argument("channel")
    p.add_argument("ts")
    p.add_argument("emoji")

    # users
    sub.add_parser("users", help="List users")

    # upload
    p = sub.add_parser("upload", help="Upload file")
    p.add_argument("channel")
    p.add_argument("filepath")
    p.add_argument("--title", default=None)

    # update
    p = sub.add_parser("update", help="Update message")
    p.add_argument("channel")
    p.add_argument("ts")
    p.add_argument("new_text")

    # delete
    p = sub.add_parser("delete", help="Delete message")
    p.add_argument("channel")
    p.add_argument("ts")

    args = parser.parse_args()
    json_mode = args.json

    if not args.command:
        parser.print_help()
        return

    try:
        bot = SlackBot()
    except ValueError as e:
        print(str(e))
        sys.exit(1)

    # Dispatch
    if args.command == "test":
        result = bot.test_connection()
        if json_mode:
            _print_json(result)
        elif result["ok"]:
            print(f"✅ Connected!")
            print(f"   Bot:  {result['bot_name']}")
            print(f"   Team: {result['team']}")
            print(f"   ID:   {result['bot_id']}")
            print(f"   URL:  {result['url']}")
        else:
            print(f"❌ Failed: {result['error']}")

    elif args.command == "channels":
        channels = bot.list_channels(limit=args.limit)
        if isinstance(channels, dict) and "error" in channels:
            print(f"❌ {channels['error']}")
        elif json_mode:
            _print_json([{"name": c["name"], "id": c["id"], "members": c.get("num_members", 0)} for c in channels])
        else:
            print(f"\n📋 Channels ({len(channels)}):")
            for ch in channels:
                print(f"   #{ch['name']:30s}  ID: {ch['id']}  Members: {ch.get('num_members', '?')}")

    elif args.command == "find-channel":
        cid = bot.find_channel_id(args.name)
        if json_mode:
            _print_json({"name": args.name, "id": cid})
        elif cid:
            print(f"✅ #{args.name} → {cid}")
        else:
            print(f"❌ Channel #{args.name} not found")

    elif args.command == "send":
        result = bot.send_message(args.channel, args.text)
        if json_mode:
            _print_json(result)
        elif result["ok"]:
            print(f"✅ Sent to {result['channel']} (ts: {result['ts']})")
        else:
            print(f"❌ {result['error']}")

    elif args.command == "send-rich":
        fields = json.loads(args.fields)
        result = bot.send_rich_message(args.channel, args.title, fields, args.color)
        if json_mode:
            _print_json(result)
        elif result["ok"]:
            print(f"✅ Rich message sent (ts: {result['ts']})")
        else:
            print(f"❌ {result['error']}")

    elif args.command == "send-blocks":
        blocks = json.loads(args.blocks)
        result = bot.send_blocks_message(args.channel, blocks, args.text)
        if json_mode:
            _print_json(result)
        elif result["ok"]:
            print(f"✅ Block message sent (ts: {result['ts']})")
        else:
            print(f"❌ {result['error']}")

    elif args.command == "market-alert":
        result = bot.send_market_alert(args.channel, args.sp500, args.vix, args.oil)
        if json_mode:
            _print_json(result)
        elif result["ok"]:
            print(f"✅ Market alert sent (ts: {result['ts']})")
        else:
            print(f"❌ {result['error']}")

    elif args.command == "read":
        messages = bot.read_messages(args.channel, limit=args.limit, hours=args.hours)
        if isinstance(messages, dict) and "error" in messages:
            print(f"❌ {messages['error']}")
        elif json_mode:
            _print_json(messages)
        else:
            print(f"\n💬 Messages ({len(messages)}):")
            print("-" * 60)
            for msg in reversed(messages):
                ts = datetime.fromtimestamp(float(msg["ts"]))
                user = msg.get("username", msg.get("user", "bot"))
                text = msg.get("text", "")[:200]
                print(f"  [{ts.strftime('%m-%d %H:%M')}] {user}: {text}")
                print(f"    ts: {msg['ts']}")
            print("-" * 60)

    elif args.command == "reply":
        result = bot.reply_to_thread(args.channel, args.thread_ts, args.text)
        if json_mode:
            _print_json(result)
        elif result["ok"]:
            print(f"✅ Replied (ts: {result['ts']})")
        else:
            print(f"❌ {result['error']}")

    elif args.command == "react":
        result = bot.add_reaction(args.channel, args.ts, args.emoji)
        if json_mode:
            _print_json(result)
        elif result["ok"]:
            print(f"✅ Added :{args.emoji}:")
        else:
            print(f"❌ {result['error']}")

    elif args.command == "users":
        users = bot.list_users()
        if isinstance(users, dict) and "error" in users:
            print(f"❌ {users['error']}")
        elif json_mode:
            _print_json([{"name": u["real_name"], "username": u["name"], "id": u["id"]} for u in users])
        else:
            print(f"\n👥 Users ({len(users)}):")
            for u in users:
                print(f"   {u.get('real_name','?'):25s}  @{u['name']:20s}  ID: {u['id']}")

    elif args.command == "upload":
        result = bot.upload_file(args.channel, args.filepath, args.title)
        if json_mode:
            _print_json(result)
        elif result["ok"]:
            print(f"✅ File uploaded")
        else:
            print(f"❌ {result['error']}")

    elif args.command == "update":
        result = bot.update_message(args.channel, args.ts, args.new_text)
        if json_mode:
            _print_json(result)
        elif result["ok"]:
            print(f"✅ Message updated")
        else:
            print(f"❌ {result['error']}")

    elif args.command == "delete":
        result = bot.delete_message(args.channel, args.ts)
        if json_mode:
            _print_json(result)
        elif result["ok"]:
            print(f"✅ Message deleted")
        else:
            print(f"❌ {result['error']}")


if __name__ == "__main__":
    main()
