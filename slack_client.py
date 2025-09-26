import os as _os
from typing import List as _List
from dataclasses import dataclass as _dataclass

import streamlit as _st
from slack_sdk import WebClient as _WebClient
from slack_sdk.errors import SlackApiError as _SlackApiError


# -------------------------
# 例外クラス
# -------------------------
class SetupError(Exception):
    """トークンなどの設定不備"""
    pass

@_dataclass
class SlackCallError(Exception):
    """Slack API 呼び出し失敗時のエラー"""
    code: str
    message: str
    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


# -------------------------
# トークン読み込み
# -------------------------
_token = _os.getenv("SLACK_BOT_TOKEN") or _st.secrets.get("SLACK_BOT_TOKEN")
if not _token:
    raise SetupError("SLACK_BOT_TOKEN が見つかりません。環境変数または st.secrets に設定してください。")

_client = _WebClient(token=_token)


def _raise_from(e: _SlackApiError):
    """SlackApiErrorをSlackCallErrorに変換して投げる"""
    data = e.response.data if hasattr(e, "response") else {}
    raise SlackCallError(code=data.get("error", "unknown_error"), message=str(e))


# -------------------------
# メッセージ投稿関数
# -------------------------
def post_reaction_poll(channel_id: str, title: str, options: _List[str]) -> str:
    """
    候補ごとに個別のメッセージを投稿し、各メッセージに ✅ / ❌ リアクションを付与する。
    戻り値は最初の投稿のURL。
    """
    if not channel_id.startswith(("C", "G", "D")):
        raise SetupError("チャンネルIDは C/G/D で始まるIDを指定してください。#名前では送れません。")

    first_url = None
    for i, opt in enumerate(options, 1):
        text = f"*{title}* 候補 {i}: {opt}\n✅=参加可 / ❌=不可"
        try:
            resp = _client.chat_postMessage(channel=channel_id, text=text)
            ts = resp["ts"]
            ch = resp["channel"]
            # 各メッセージに ✅ と ❌ を追加
            _client.reactions_add(channel=ch, timestamp=ts, name="white_check_mark")
            _client.reactions_add(channel=ch, timestamp=ts, name="x")
            if first_url is None:
                first_url = f"https://app.slack.com/client/{resp['team']}/{ch}/p{str(ts).replace('.', '')}"
        except _SlackApiError as e:
            _raise_from(e)

    return first_url or ""


def send_final_decision(channel_id: str, message: str) -> str:
    """
    最終決定をSlackに通知する
    """
    try:
        resp = _client.chat_postMessage(channel=channel_id, text=message)
        ts = resp["ts"]
        ch = resp["channel"]
        url = f"https://app.slack.com/client/{resp['team']}/{ch}/p{str(ts).replace('.', '')}"
        return url
    except _SlackApiError as e:
        _raise_from(e)


def get_user_display_name(user_id: str) -> str:
    """
    ユーザーIDから表示名を取得する
    """
    try:
        info = _client.users_info(user=user_id)
        prof = info.get("user", {}).get("profile", {})
        return prof.get("display_name") or prof.get("real_name") or user_id
    except _SlackApiError:
        return user_id
