import os as _os
from typing import List as _List
from dataclasses import dataclass as _dataclass

import streamlit as _st
from slack_sdk import WebClient as _WebClient
from slack_sdk.errors import SlackApiError as _SlackApiError


class SetupError(Exception):
    pass

@_dataclass
class SlackCallError(Exception):
    code: str
    message: str
    def __str__(self) -> str:
        return f"{self.code}: {self.message}"

# --- Token 読み込み（env か secrets のどちらでもOK） ---
_token = _os.getenv("SLACK_BOT_TOKEN") or _st.secrets.get("SLACK_BOT_TOKEN")
if not _token:
    raise SetupError("SLACK_BOT_TOKEN が見つかりません。環境変数または st.secrets に設定してください。")
_client = _WebClient(token=_token)


def _raise_from(e: _SlackApiError):
    data = e.response.data if hasattr(e, "response") else {}
    raise SlackCallError(code=data.get("error", "unknown_error"), message=str(e))


def post_reaction_poll(channel_id: str, title: str, options: _List[str]) -> str:
    """候補を列挙したメッセージを投稿し、✅/❌リアクションを付ける。戻り値はメッセージURL。"""
    if not channel_id.startswith(("C", "G", "D")):
        raise SetupError("チャンネルIDは C/G/D で始まるIDを指定してください。#名前では送れません。")

    body_lines = [f"*{title}*", "投票方法: ✅=参加可 / ❌=不可", ""]
    for i, opt in enumerate(options, 1):
        body_lines.append(f"{i}. {opt}")
    text = "\n".join(body_lines)

    try:
        resp = _client.chat_postMessage(channel=channel_id, text=text)
        ts = resp["ts"]
        ch = resp["channel"]
        # 投稿に対してボットがリアクションを先付け
        _client.reactions_add(channel=ch, timestamp=ts, name="white_check_mark")
        _client.reactions_add(channel=ch, timestamp=ts, name="x")
        # メッセージURL（Slack標準フォーマット）
        url = f"https://app.slack.com/client/{resp['team']}/{ch}/p{str(ts).replace('.', '')}"
        return url
    except _SlackApiError as e:
        _raise_from(e)


def send_final_decision(channel_id: str, message: str) -> str:
    try:
        resp = _client.chat_postMessage(channel=channel_id, text=message)
        ts = resp["ts"]
        ch = resp["channel"]
        url = f"https://app.slack.com/client/{resp['team']}/{ch}/p{str(ts).replace('.', '')}"
        return url
    except _SlackApiError as e:
        _raise_from(e)


def get_user_display_name(user_id: str) -> str:
    try:
        info = _client.users_info(user=user_id)
        prof = info.get("user", {}).get("profile", {})
        return prof.get("display_name") or prof.get("real_name") or user_id
    except _SlackApiError:
        return user_id
