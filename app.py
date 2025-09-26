import streamlit as st
import pandas as pd
import datetime
import db       # db.py
import slack_client # slack_client.py

#Streamlit UI
db.init_db()
st.title("📅 Slack日程調整アプリ")

#セッションステートの初期化
if 'active_meeting_info' not in st.session_state:
    st.session_state.active_meeting_info = None

if 'candidates_ui' not in st.session_state:
    st.session_state.candidates_ui = [
        {'date': datetime.date.today(), 'time': datetime.time(10, 0)},
        {'date': datetime.date.today() + datetime.timedelta(days=1), 'time': datetime.time(10, 0)}
    ]

tab1, tab2 = st.tabs(["投票の作成", "結果の確認・確定"])

#Tab 1：投票の作成
with tab1:
    st.header("新しい投票を作成")
    channel_id = st.text_input("投稿先のチャンネルID")
    st.info("""
    **チャンネルIDの取得方法:**
    1. Slackでチャンネル名を右クリック → 2. 「リンクをコピー」
    3. リンク末尾の `C` から始まる文字列を貼り付け
    """)
    title = st.text_input("投票タイトル", "次回のミーティング日程")
    st.subheader("候補日時を選択")

    #候補日の作成
    final_candidates_list = []
    for i, candidate in enumerate(st.session_state.candidates_ui):
        st.markdown("---")
        st.markdown(f"**候補 {i+1}**")
        cols = st.columns(2)
        new_date = cols[0].date_input("日付", value=candidate['date'], key=f"date_{i}")
        new_time = cols[1].time_input("時刻", value=candidate['time'], key=f"time_{i}")
        # UIの変更をセッションに反映
        st.session_state.candidates_ui[i] = {'date': new_date, 'time': new_time}
        # Slack送信用リストを作成
        final_candidates_list.append(datetime.datetime.combine(new_date, new_time).strftime('%Y/%m/%d(%a) %H:%M'))

    col_add, col_del = st.columns(2)
    if col_add.button("＋ 候補を追加"):
        st.session_state.candidates_ui.append({'date': datetime.date.today(), 'time': datetime.time(10, 0)})
        st.rerun()
    if len(st.session_state.candidates_ui) > 2 and col_del.button("－ 最後の候補を削除"):
        st.session_state.candidates_ui.pop()
        st.rerun()

    st.markdown("---")
    if st.button("この内容でSlackに投票を投稿", type="primary"):
        if channel_id and final_candidates_list:
            try:
                meeting_id = db.create_meeting(title, channel_id)
                
                options_with_id = []
                for cand_text in final_candidates_list:
                    option_id = db.add_option(cand_text, meeting_id)
                    options_with_id.append((option_id, cand_text))

                ts_map = slack_client.post_reaction_poll(
                    title=title,
                    options=options_with_id,
                    channel=channel_id
                )
                
                st.session_state.active_meeting_info = {
                    "meeting_id": meeting_id,
                    "title": title,
                    "channel_id": channel_id,
                    "ts_map": ts_map
                }

                st.success(f"✅ Slackに投票を投稿しました！")
                st.info("「結果の確認・確定」タブから結果を確認してください。")

            except Exception as e:
                st.error(f"❌ エラーが発生しました: {e}")

#Tab 2：結果の確認・確定
with tab2:
    st.header("投票結果の確認")

    active_meeting = st.session_state.active_meeting_info

    if not active_meeting:
        st.warning("現在アクティブな投票はありません。まずは「投票の作成」タブで新しい投票を作成してください。")
    else:
        meeting_id = active_meeting['meeting_id']
        channel_id = active_meeting['channel_id']
        ts_map = active_meeting['ts_map']
        
        st.subheader(f"投票タイトル: {active_meeting['title']}")
        
        if st.button("現在の投票状況"):
            try:
                options_from_db = db.list_options(meeting_id)
                votes = slack_client.get_reaction_votes(channel_id, ts_map)
                
                pretty_results = {}
                options_dict = dict(options_from_db)

                for oid, result in votes.items():
                    ok_names = [slack_client.get_user_display_name(uid) for uid in result.get("ok", [])]
                    ng_names = [slack_client.get_user_display_name(uid) for uid in result.get("ng", [])]
                    text = options_dict.get(oid, f"不明なID {oid}")
                    pretty_results[text] = {"参加": ok_names, "不可": ng_names}
                
                st.write("現在の投票状況")
                st.json(pretty_results)

                st.session_state.results_to_confirm = pretty_results
            
            except Exception as e:
                st.error(f"❌ 処理中にエラーが発生しました: {e}")
    
        if 'results_to_confirm' in st.session_state:
            pretty_results = st.session_state.results_to_confirm
            st.subheader("確定候補の選択")
            final_candidate = st.radio(
                "最終確定する日程を選択してください。",
                options=pretty_results.keys(),
                index=None
            )
            meeting_url = st.text_input("会議URL（任意）")

            if final_candidate and st.button("この内容でSlackに確定を通知", type="primary"):
                message = f"📣 会議日程が決定しました：*{final_candidate}* です！"
                if meeting_url:
                    message += f"\n会議URL: {meeting_url}"
                slack_client.send_final_decision(channel_id, message)
                st.success("Slackに確定日程を通知しました！")
                
                st.session_state.active_meeting_info = None
                del st.session_state.results_to_confirm

                st.rerun()
