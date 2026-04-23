import json
import os
from datetime import date, datetime

import pandas as pd
import streamlit as st

DATA_FILE = "engen_streamlit_data.json"

DEFAULT_DATA = {
    "base_cigs_per_day": 20,
    "target_cigs_per_day": 10,
    "pack_price": 600,
    "cigs_per_pack": 20,
    "records": {},
}


# ---------- データ処理 ----------
def load_data():
    if not os.path.exists(DATA_FILE):
        return DEFAULT_DATA.copy()

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = DEFAULT_DATA.copy()
        merged.update(data)
        if "records" not in merged or not isinstance(merged["records"], dict):
            merged["records"] = {}
        return merged
    except Exception:
        return DEFAULT_DATA.copy()



def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)



def get_today_str():
    return date.today().isoformat()



def ensure_today_record(data):
    today = get_today_str()
    if today not in data["records"]:
        data["records"][today] = {
            "count": 0,
            "manual_saved_override": None,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
    return today



def one_cig_price(data):
    cigs_per_pack = data.get("cigs_per_pack", 20)
    if cigs_per_pack <= 0:
        return 0
    return data.get("pack_price", 0) / cigs_per_pack



def calculate_day_stats(data, day_str):
    record = data["records"].get(day_str, {"count": 0, "manual_saved_override": None})
    count = int(record.get("count", 0))
    one_price = one_cig_price(data)
    base = int(data.get("base_cigs_per_day", 0))
    target = int(data.get("target_cigs_per_day", 0))

    today_cost = count * one_price
    base_cost = base * one_price
    target_cost = target * one_price
    saved_vs_base = max(base_cost - today_cost, 0)
    current_cig_cost = count * one_price
    remaining_to_target = max(target - count, 0)
    over_target = max(count - target, 0)

    return {
        "count": count,
        "one_price": one_price,
        "today_cost": today_cost,
        "base_cost": base_cost,
        "target_cost": target_cost,
        "saved_vs_base": saved_vs_base,
        "current_cig_cost": current_cig_cost,
        "remaining_to_target": remaining_to_target,
        "over_target": over_target,
    }



def calculate_totals(data):
    total_count = 0
    total_cost = 0.0
    total_saved = 0.0

    for day_str in data["records"]:
        stats = calculate_day_stats(data, day_str)
        total_count += stats["count"]
        total_cost += stats["today_cost"]
        total_saved += stats["saved_vs_base"]

    return {
        "total_count": total_count,
        "total_cost": total_cost,
        "total_saved": total_saved,
    }



def make_history_df(data):
    rows = []
    for day_str in sorted(data["records"].keys()):
        stats = calculate_day_stats(data, day_str)
        rows.append(
            {
                "日付": day_str,
                "吸った本数": stats["count"],
                "使った金額": round(stats["today_cost"], 1),
                "元のペースなら": round(stats["base_cost"], 1),
                "節約額": round(stats["saved_vs_base"], 1),
            }
        )

    if not rows:
        return pd.DataFrame(columns=["日付", "吸った本数", "使った金額", "元のペースなら", "節約額"])

    df = pd.DataFrame(rows)
    df["日付"] = pd.to_datetime(df["日付"])
    df = df.sort_values("日付")
    return df


# ---------- 画面 ----------
st.set_page_config(page_title="減煙アプリ", page_icon="🚬", layout="centered")
st.title("🚬 減煙アプリ")
st.caption("スマホでも操作できる、自分用の減煙記録アプリ")

if "data" not in st.session_state:
    st.session_state.data = load_data()

data = st.session_state.data
today = ensure_today_record(data)
save_data(data)

# ---------- 基本設定 ----------
st.subheader("基本設定")
with st.form("settings_form"):
    base_cigs = st.number_input(
        "元々1日に吸っていた本数",
        min_value=0,
        value=int(data.get("base_cigs_per_day", 20)),
        step=1,
    )
    target_cigs = st.number_input(
        "今の目標本数（1日）",
        min_value=0,
        value=int(data.get("target_cigs_per_day", 10)),
        step=1,
    )
    pack_price = st.number_input(
        "1箱の値段（円）",
        min_value=0.0,
        value=float(data.get("pack_price", 600)),
        step=10.0,
    )
    cigs_per_pack = st.number_input(
        "1箱の本数",
        min_value=1,
        value=int(data.get("cigs_per_pack", 20)),
        step=1,
    )
    settings_submit = st.form_submit_button("設定を保存")

if settings_submit:
    data["base_cigs_per_day"] = int(base_cigs)
    data["target_cigs_per_day"] = int(target_cigs)
    data["pack_price"] = float(pack_price)
    data["cigs_per_pack"] = int(cigs_per_pack)
    save_data(data)
    st.success("設定を保存したよ")

# ---------- 今日の状態 ----------
st.subheader("今日の状態")
st.write(f"日付: {today}")

today_stats = calculate_day_stats(data, today)

col1, col2 = st.columns(2)
col3, col4 = st.columns(2)

col1.metric("今日吸った本数", f"{today_stats['count']}本")
col2.metric("1本あたり", f"{today_stats['one_price']:.1f}円")
col3.metric("今日使った金額", f"{today_stats['today_cost']:.1f}円")
col4.metric("今日の節約額", f"{today_stats['saved_vs_base']:.1f}円")

col5, col6 = st.columns(2)
col7, col8 = st.columns(2)
col5.metric("今吸ったタバコで", f"{today_stats['current_cig_cost']:.1f}円目")
col6.metric("元のペースなら", f"{today_stats['base_cost']:.1f}円")
col7.metric("目標まで残り", f"{today_stats['remaining_to_target']}本")
col8.metric("目標超過", f"{today_stats['over_target']}本")

if today_stats["count"] == 0:
    st.info("まだ今日は吸ってないね。いいスタート。")
elif today_stats["count"] <= data["target_cigs_per_day"]:
    st.success("目標ペース内。かなりいい感じ。")
else:
    st.warning("今日は目標を超えてる。次の1本を少しだけ遅らせてみよう。")

# ---------- 操作ボタン ----------
st.subheader("操作")
button_col1, button_col2, button_col3 = st.columns(3)

if button_col1.button("吸った", use_container_width=True):
    data["records"][today]["count"] += 1
    data["records"][today]["updated_at"] = datetime.now().isoformat(timespec="seconds")
    save_data(data)
    st.rerun()

if button_col2.button("1本取り消し", use_container_width=True):
    if data["records"][today]["count"] > 0:
        data["records"][today]["count"] -= 1
        data["records"][today]["updated_at"] = datetime.now().isoformat(timespec="seconds")
        save_data(data)
    st.rerun()

if button_col3.button("今日を0本にする", use_container_width=True):
    data["records"][today]["count"] = 0
    data["records"][today]["updated_at"] = datetime.now().isoformat(timespec="seconds")
    save_data(data)
    st.rerun()

# ---------- 手動入力 ----------
st.subheader("今日の本数を直接入力")
manual_count = st.number_input(
    "今日吸った本数",
    min_value=0,
    value=int(data["records"][today]["count"]),
    step=1,
)

if st.button("本数を反映"):
    data["records"][today]["count"] = int(manual_count)
    data["records"][today]["updated_at"] = datetime.now().isoformat(timespec="seconds")
    save_data(data)
    st.success("今日の本数を更新したよ")
    st.rerun()

# ---------- 累計 ----------
st.subheader("累計")
totals = calculate_totals(data)

total_col1, total_col2, total_col3 = st.columns(3)
total_col1.metric("累計本数", f"{totals['total_count']}本")
total_col2.metric("累計使用額", f"{totals['total_cost']:.1f}円")
total_col3.metric("累計節約額", f"{totals['total_saved']:.1f}円")

# ---------- 履歴とグラフ ----------
st.subheader("履歴")
df = make_history_df(data)

if not df.empty:
    show_df = df.copy()
    show_df["日付"] = show_df["日付"].dt.strftime("%Y-%m-%d")
    st.dataframe(show_df, use_container_width=True, hide_index=True)

    st.subheader("グラフ")
    chart_df = df.set_index("日付")[["吸った本数", "節約額"]]
    st.line_chart(chart_df)

    st.bar_chart(df.set_index("日付")[["吸った本数"]])
else:
    st.info("まだ履歴がないよ。今日の記録から始めよう。")

# ---------- 外でも使うための説明 ----------
st.subheader("外でも使いたいとき")
st.markdown(
    """
- 今のままでも、**Macを起動していて同じWi-Fi**ならスマホで使える
- **スマホ単体でどこでも使いたい**なら、Render か Streamlit Community Cloud に公開する
- 公開すれば、SafariでURLを開くだけで使えるようになる
"""
)

st.caption("データは app.py と同じフォルダの engen_streamlit_data.json に保存されるよ")
