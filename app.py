import os
import datetime as dt
import streamlit as st

import db
import slack_client

st.set_page_config(page_title="Slack連携 日程調整", page_icon="🗓️", layout="centered")
db.init_db()

st.title("📅 Slack日程調整アプリ（修正版）")

with st.expander("デバッグ情報", expanded=False):
    st.write({
        "ENV_SLACK_BOT_TOKEN": bool(os.getenv("SLACK_BOT_TOKEN")),
        "SECRETS_SLACK_BOT_TOKEN": bool(st.secrets.get("SLACK_BOT_TOKEN")) if hasattr(st, "secrets") else False,
    })

# --- 入力欄 ---
channel_id = st.text_input("Slack チャンネルID (例: CXXXXXXXX)")
meeting_title = st.text_input("投票タイトル", value="次回ミーティング候補")

if "candidates_ui" not in st.session_state:
    st.session_state.candidates_ui = [
        {"date": dt.date.today(), "time": dt.time(10, 0)},
        {"date": dt.date.today(), "time": dt.time(14, 0)},
    ]

st.subheader("候補の編集")
for i, row in enumerate(st.session_state.candidates_ui):
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        st.session_state.candidates_ui[i]["date"] = st.date_input(f"日付 #{i+1}", row["date"], key=f"d_{i}")
    with c2:
        st.session_state.candidates_ui[i]["time"] = st.time_input(f"時刻 #{i+1}", row["time"], key=f"t_{i}")
    with c3:
        if st.button("削除", key=f"del_{i}"):
            st.session_state.candidates_ui.pop(i)
            st.rerun()

col_add, col_dummy = st.columns([1, 2])
if col_add.button("＋ 候補を追加"):
    st.session_state.candidates_ui.append({"date": dt.date.today(), "time": dt.time(16, 0)})

# 送信用に文字列へ整形
options_list: list[str] = []
for row in st.session_state.candidates_ui:
    options_list.append(dt.datetime.combine(row["date"], row["time"]).strftime("%Y/%m/%d(%a) %H:%M"))

st.markdown("---")
submit = st.button("この内容でSlackに投票を投稿", type="primary")

if submit:
    if not channel_id:
        st.error("チャンネルIDを入力してください。例: CXXXXXXXX")
    elif not options_list:
        st.error("候補を1つ以上追加してください。")
    else:
        try:
            post_url = slack_client.post_reaction_poll(channel_id=channel_id, title=meeting_title, options=options_list)
            st.success("Slackに投稿しました！")
            st.write("メッセージURL:", post_url)
        except slack_client.SetupError as e:
            st.error(f"設定エラー: {e}")
        except slack_client.SlackCallError as e:
            st.error(f"Slack API エラー: {e.message} ({e.code})")
        except Exception as e:
            st.exception(e)

st.markdown("---")

st.subheader("確定通知（任意）")
final_candidate = st.selectbox("確定する候補を選択", [""] + options_list)
meeting_url = st.text_input("会議URL（任意）")
if st.button("この内容でSlackに確定を通知"):
    if not channel_id:
        st.error("チャンネルIDを入力してください。")
    elif not final_candidate:
        st.error("確定候補を選択してください。")
    else:
        msg = f"📣 会議日程が決定しました：*{final_candidate}* です！"
        if meeting_url:
            msg += f"\n会議URL: {meeting_url}"
        try:
            url = slack_client.send_final_decision(channel_id, msg)
            st.success("Slackに確定日程を通知しました！")
            st.write("メッセージURL:", url)
        except Exception as e:
            st.exception(e)
