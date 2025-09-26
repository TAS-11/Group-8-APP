import os
from typing import List, Tuple, Dict
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Slackクライアントの初期化
slack_token = os.getenv("SLACK_BOT_TOKEN")
client = WebClient(token=slack_token)


# --- 旧来のボタン方式（FastAPIが必要になる） ---
def send_candidates(meeting_id, title, options, channel_id):
    """
    候補日程をSlackに送信する関数（ボタン形式）
    """
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*会議タイトル:* {title}\n候補日程を選択してください。"
            }
        }
    ]

    for option_id, option_text in options:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"候補: {option_text}"},
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "参加"},
                "value": f"{meeting_id}|{option_id}|yes",
                "action_id": "vote_yes"
            }
        })
        blocks.append({
            "type": "section",
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "不可"},
                "value": f"{meeting_id}|{option_id}|no",
                "action_id": "vote_no"
            }
        })
        blocks.append({"type": "divider"})

    try:
        response = client.chat_postMessage(
            channel=channel_id,
            text=f"会議「{title}」の候補日程です。",
            blocks=blocks
        )
        return response
    except SlackApiError as e:
        print(f"Error sending candidates: {e.response['error']}")
        return None


def send_final_decision(channel_id, option_text):
    """
    最終決定をSlackに送信する関数
    """
    try:
        response = client.chat_postMessage(
            channel=channel_id,
            text=f"✅ 最終決定: {option_text}"
        )
        return response
    except SlackApiError as e:
        print(f"Error sending final decision: {e.response['error']}")
        return None


def get_user_display_name(user_id):
    """
    Slackユーザーの表示名を取得
    """
    try:
        response = client.users_info(user=user_id)
        user = response["user"]
        return user.get("profile", {}).get("display_name") or user.get("real_name", "Unknown")
    except SlackApiError as e:
        print(f"Error fetching user info: {e.response['error']}")
        return "Unknown"


# --- 新方式: リアクション投票（FastAPI不要） ---
def post_reaction_poll(title: str, options: List[Tuple[int, str]], channel: str) -> Dict[int, str]:
    """
    各候補を「1メッセージ＝1候補」で投稿し、投票用リアクションを付ける。
    return: {option_id: message_ts}
    """
    ts_map = {}
    try:
        # 見出し
        client.chat_postMessage(channel=channel, text=f"📊 *{title}*（✅=参加 / ❌=不可）")
        for oid, label in options:
            resp = client.chat_postMessage(channel=channel, text=f"候補: {label}")
            ts = resp["ts"]
            ts_map[oid] = ts
            # 投票用リアクションを事前にBotが付けておくと便利
            try:
                client.reactions_add(channel=channel, name="white_check_mark", timestamp=ts)
                client.reactions_add(channel=channel, name="x", timestamp=ts)
            except SlackApiError:
                pass  # 既にリアクションが存在する場合などは無視
    except SlackApiError as e:
        print(f"Error posting reaction poll: {e.response['error']}")
    return ts_map


def get_reaction_votes(channel: str, ts_map: Dict[int, str]) -> Dict[int, Dict[str, list]]:
    """
    Slackからリアクションを読み取り、各候補の参加/不可ユーザーを返す。
    return: {option_id: {"ok": [user_ids], "ng": [user_ids]}}
    """
    result = {}
    for oid, ts in ts_map.items():
        try:
            info = client.conversations_history(
                channel=channel, latest=ts, oldest=ts, inclusive=True, limit=1
            )
            messages = info.get("messages", [])
            ok_users, ng_users = [], []
            if messages:
                reactions = messages[0].get("reactions", [])
                for r in reactions:
                    if r.get("name") in ("white_check_mark", "heavy_check_mark"):
                        ok_users.extend(r.get("users", []))
                    if r.get("name") in ("x", "negative_squared_cross_mark"):
                        ng_users.extend(r.get("users", []))
            result[oid] = {"ok": list(set(ok_users)), "ng": list(set(ng_users))}
        except SlackApiError as e:
            print(f"Error fetching reactions: {e.response['error']}")
            result[oid] = {"ok": [], "ng": []}
    return result
