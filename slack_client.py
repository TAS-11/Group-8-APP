import os
from typing import List, Tuple, Optional
from slack_sdk import WebClient
from slack_sdk.webhook import WebhookClient
from dotenv import load_dotenv
from slack_sdk.errors import SlackApiError

load_dotenv()

def get_user_display_name(user_id: str) -> str:
    bot_token = os.getenv("SLACK_BOT_TOKEN", "")
    if not bot_token:
        return user_id

    client = WebClient(token=bot_token)
    try:
        response = client.users_info(user=user_id)
        if response["ok"]:
            profile = response["user"]["profile"]
            return profile.get("display_name") or profile.get("real_name") or user_id
    except SlackApiError as e:
        print(f"Slack API error: {e.response['error']}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    return user_id

def _blocks_for_options(options: List[Tuple[int, str]]):
    blocks = []
    for oid, label in options:
        blocks.extend([
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{label}*"}
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "○ 参加"},
                        "style": "primary",
                        "action_id": f"vote|{oid}|yes",
                        "value": f"{oid}:ok"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "× 不可"},
                        "style": "danger",
                        "action_id": f"vote|{oid}|no",
                        "value": f"{oid}:ng"
                    }
                ]
            },
            {"type": "divider"}
        ])
    return blocks

def send_candidates(text: str, options: List[Tuple[int, str]], channel: Optional[str] = None) -> Optional[str]:
    webhook_url = os.getenv("SLACK_INCOMING_WEBHOOK_URL", "")
    bot_token = os.getenv("SLACK_BOT_TOKEN", "")
    blocks = _blocks_for_options(options)

    if bot_token:
        client = WebClient(token=bot_token)
        resp = client.chat_postMessage(
            channel=channel or os.getenv("SLACK_CHANNEL", "C09FX3UP8H1"),
            text=text,
            blocks=blocks
        )
        print(resp)
        if resp.get("ok"):
            return resp.get("ts")
        return None
    elif webhook_url:
        wh = WebhookClient(webhook_url)
        wh.send(text=text, blocks=blocks)
        return None
    else:
        raise RuntimeError("Slack credentials not provided. Set SLACK_BOT_TOKEN or SLACK_INCOMING_WEBHOOK_URL.")

def send_final_decision(message: str, channel: Optional[str] = None):
    webhook_url = os.getenv("SLACK_INCOMING_WEBHOOK_URL", "")
    bot_token = os.getenv("SLACK_BOT_TOKEN", "")
    if bot_token:
        client = WebClient(token=bot_token)
        client.chat_postMessage(channel=channel or os.getenv("SLACK_CHANNEL", "C09FX3UP8H1"), text=message)
    elif webhook_url:
        WebhookClient(webhook_url).send(text=message)
    else:
        raise RuntimeError("Slack credentials not provided. Set SLACK_BOT_TOKEN or SLACK_INCOMING_WEBHOOK_URL.")
