import os as _os
from typing import List as _List
from dataclasses import dataclass as _dataclass

import streamlit as _st
from slack_sdk import WebClient as _WebClient
from slack_sdk.errors import SlackApiError as _SlackApiError

class SetupError(Exception): pass

@_dataclass
class SlackCallError(Exception):
    code: str; message: str
    def __str__(self): return f"{self.code}: {self.message}"

_token = _os.getenv("SLACK_BOT_TOKEN") or _st.secrets.get("SLACK_BOT_TOKEN")
if not _token: raise SetupError("SLACK_BOT_TOKEN が見つかりません。")
_client = _WebClient(token=_token)

_bot_user_id_cache: str | None = None

def _get_bot_user_id() -> str | None:
    global _bot_user_id_cache
    if _bot_user_id_cache:
        return _bot_user_id_cache
    try:
        info = _client.auth_test()
        _bot_user_id_cache = info.get("user_id")
        return _bot_user_id_cache
    except _SlackApiError:
        return None

def _raise_from(e: _SlackApiError):
    data = e.response.data if hasattr(e, "response") else {}
    raise SlackCallError(code=data.get("error", "unknown_error"), message=str(e))

def post_reaction_poll(channel_id: str, title: str, options: _List[str]) -> str:
    if not channel_id.startswith(("C","G","D")): raise SetupError("チャンネルIDは C/G/D から")
    first_url = None
    for i,opt in enumerate(options,1):
        text = f"*{title}* 候補 {i}: {opt}\n✅=参加可 / ❌=不可"
        try:
            resp = _client.chat_postMessage(channel=channel_id, text=text)
            ts, ch = resp["ts"], resp["channel"]
            _client.reactions_add(channel=ch, timestamp=ts, name="white_check_mark")
            _client.reactions_add(channel=ch, timestamp=ts, name="x")
            if first_url is None:
                first_url = f"https://app.slack.com/client/{resp['team']}/{ch}/p{str(ts).replace('.','')}"
        except _SlackApiError as e: _raise_from(e)
    return first_url or ""

def send_final_decision(channel_id: str, message: str) -> str:
    try:
        resp = _client.chat_postMessage(channel=channel_id, text=message)
        ts, ch = resp["ts"], resp["channel"]
        return f"https://app.slack.com/client/{resp['team']}/{ch}/p{str(ts).replace('.','')}"
    except _SlackApiError as e: _raise_from(e)

def get_user_display_name(user_id: str) -> str:
    try:
        info = _client.users_info(user=user_id)
        prof = info.get("user",{}).get("profile",{})
        return prof.get("display_name") or prof.get("real_name") or user_id
    except _SlackApiError: return user_id

def _parse_option_from_text(title: str, text: str) -> str | None:
    import re
    pat = rf"\*{re.escape(title)}\*\s*候補\s*\d+\s*:\s*(.+)"
    m = re.search(pat, text)
    return m.group(1).strip() if m else None

def fetch_poll_results(channel_id: str, title: str, lookback_hours: int = 168) -> list[dict]:
    import time
    oldest = int(time.time()) - lookback_hours * 3600
    results = {}
    bot_uid = _get_bot_user_id()

    try:
        resp = _client.conversations_history(channel=channel_id, oldest=oldest, limit=200, inclusive=True)
    except _SlackApiError as e: _raise_from(e)

    for msg in resp.get("messages", []):
        text = msg.get("text","") or ""
        opt = _parse_option_from_text(title, text)
        if not opt: continue
        yes_ids, no_ids = [], []
        for r in (msg.get("reactions") or []):
            if r.get("name")=="white_check_mark": yes_ids += (r.get("users") or [])
            elif r.get("name")=="x": no_ids += (r.get("users") or [])
        if bot_uid:
            yes_ids = [u for u in yes_ids if u != bot_uid]
            no_ids  = [u for u in no_ids  if u != bot_uid]
        yes_names = [get_user_display_name(u) for u in yes_ids]
        no_names  = [get_user_display_name(u) for u in no_ids]
        results[opt] = {
            "option": opt,
            "yes_count": len(set(yes_ids)),
            "no_count": len(set(no_ids)),
            "yes_names": sorted(set(yes_names)),
            "no_names": sorted(set(no_names)),
            "ts": msg.get("ts")
        }
    return sorted(results.values(), key=lambda d: d.get("ts") or "")
