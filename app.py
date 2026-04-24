import json
import os
import re
import hashlib
from datetime import datetime

import pandas as pd
import pytz
import streamlit as st

JAPAN_TZ = pytz.timezone("Asia/Tokyo")

DEFAULT_DATA = {
    "password_hash": "",
    "base_cigs_per_day": 20,
    "target_cigs_per_day": 10,
    "pack_price": 600,
    "cigs_per_pack": 20,
    "records": {},
}


# ---------- ユーザー処理 ----------
def safe_username(name):
    name = name.strip().lower()
    name = re.sub(r"[^a-zA-Z0-9_\-ぁ-んァ-ン一-龥]", "_", name)
    return name[:30]


def get_data_file(username):
    safe_name = safe_username(username)
    return f"engen_data_{safe_name}.json"


def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# ---------- データ処理 ----------
def load_data(data_file):
    if not os.path.exists(data_file):
        return DEFAULT_DATA.copy()

    try:
        with open(data_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        merged = DEFAULT_DATA.copy()
        merged.update(data)

        if "records" not in merged or not isinstance(merged["records"], dict):
            merged["records"] = {}

        return merged
    except Exception:
        return DEFAULT_DATA.copy()


def save_data(data, data_file):
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_japan_now():
    return datetime.now(JAPAN_TZ)


def get_today_str():
    return get_japan_now().strftime("%Y-%m-%d")


def ensure_today_record(data):
    today = get_today_str()

    if today not in data["records"]:
        data["records"][today] = {
            "count": 0,
            "updated_at": get_japan_now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    return today


def get_count(data, day):
    record = data["records"].get(day, {"count": 0})

    if isinstance(record, int):
        return record

    return int(record.get("count", 0))


def set_count(data, day, count):
    if day not in data["records"] or isinstance(data["records"].get(day), int):
        data["records"][day] = {
            "count": 0,
            "updated_at": get_japan_now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    data["records"][day]["count"] = max(int(count), 0)
    data["records"][day]["updated_at"] = get_japan_now().strftime("%Y-%m-%d %H:%M:%S")


def one_cig_price(data):
    cigs_per_pack = int(data.get("cigs_per_pack", 20))
    if cigs_per_pack <= 0:
        return 0
    return float(data.get("pack_price", 0)) / cigs_per_pack


def calculate_day_stats(data, day):
    count = get_count(data, day)
    price = one_cig_price(data)
    base = int(data.get("base_cigs_per_day", 0))
    target = int(data.get("target_cigs_per_day", 0))

    actual_cost = count * price
    base_cost = base * price
    saved = max(base_cost - actual_cost, 0)
    remaining = max(target - count, 0)
    over = max(count - target, 0)

    return {
        "count": count,
        "one_price": price,
        "actual_cost": actual_cost,
        "base_cost": base_cost,
        "saved": saved,
        "remaining": remaining,
        "over": over,
    }


def calculate_total_stats(data):
    total_count = 0
    total_cost = 0
    total_saved = 0

    for day in data["records"]:
        stats = calculate_day_stats(data, day)
        total_count += stats["count"]
        total_cost += stats["actual_cost"]
        total_saved += stats["saved"]

    return {
        "total_count": total_count,
        "total_cost": total_cost,
        "total_saved": total_saved,
    }


def make_history_df(data):
    rows = []

    for day in sorted(data["records"].keys()):
        stats = calculate_day_stats(data, day)
        rows.append(
            {
                "日付": day,
                "吸った本数": stats["count"],
                "使った金額": round(stats["actual_cost"], 1),
                "節約額": round(stats["saved"], 1),
            }
        )

    if not rows:
        return pd.DataFrame(columns=["日付", "吸った本数", "使った金額", "節約額"])

    df = pd.DataFrame(rows)
    df["日付"] = pd.to_datetime(df["日付"])
    return df.sort_values("日付")


# ---------- 画面設定 ----------
st.set_page_config(
    page_title="減煙アプリ",
    page_icon="🚬",
    layout="centered",
)

st.markdown(
    """
<style>
.main-title {
    font-size: 34px;
    font-weight: 800;
    margin-bottom: 4px;
}
.sub-text {
    color: #777;
    margin-bottom: 20px;
}
.big-card {
    background: linear-gradient(135deg, #232946, #121629);
    padding: 24px;
    border-radius: 20px;
    color: white;
    text-align: center;
    margin: 12px 0 20px 0;
    box-shadow: 0 8px 24px rgba(0,0,0,0.18);
}
.big-card h1 {
    font-size: 44px;
    margin: 6px 0;
}
.big-card p {
    color: #d6d6e7;
    margin: 0;
}
.login-card {
    background-color: #f6f6fb;
    padding: 18px;
    border-radius: 18px;
    margin-bottom: 18px;
}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown('<div class="main-title">🚬 減煙アプリ</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-text">ユーザー名と合言葉で記録を分ける、スマホ対応の減煙メモ</div>', unsafe_allow_html=True)

# ---------- ログイン ----------
st.subheader("🔐 ログイン")

query_user = st.query_params.get("user", "")
if isinstance(query_user, list):
    query_user = query_user[0]

if "username" not in st.session_state:
    st.session_state.username = safe_username(query_user) if query_user else ""
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "data_file" not in st.session_state:
    st.session_state.data_file = ""

username_input = st.text_input(
    "ユーザー名",
    value=st.session_state.username,
    placeholder="例: yuto / takahide",
)

username = safe_username(username_input)

if not username:
    st.warning("まずユーザー名を入力してね。")
    st.stop()

DATA_FILE = get_data_file(username)
login_data = load_data(DATA_FILE)
is_new_user = not os.path.exists(DATA_FILE) or login_data.get("password_hash", "") == ""

if username != st.session_state.username:
    st.session_state.username = username
    st.session_state.authenticated = False
    st.session_state.data_file = DATA_FILE
    if "data" in st.session_state:
        del st.session_state.data
    st.query_params["user"] = username
    st.rerun()

st.markdown('<div class="login-card">', unsafe_allow_html=True)

if is_new_user:
    st.info("このユーザー名は初めて使われます。合言葉を登録してください。")
    new_password = st.text_input("登録する合言葉", type="password")
    new_password_confirm = st.text_input("合言葉をもう一度入力", type="password")

    if st.button("新規登録して始める", use_container_width=True):
        if len(new_password) < 3:
            st.error("合言葉は3文字以上にしてね。")
            st.stop()
        if new_password != new_password_confirm:
            st.error("合言葉が一致してないよ。")
            st.stop()

        login_data["password_hash"] = hash_password(new_password)
        save_data(login_data, DATA_FILE)

        st.session_state.authenticated = True
        st.session_state.username = username
        st.session_state.data_file = DATA_FILE
        st.session_state.data = login_data
        st.query_params["user"] = username
        st.success("登録できたよ")
        st.rerun()
else:
    password = st.text_input("合言葉", type="password")

    if st.button("ログイン", use_container_width=True):
        if hash_password(password) == login_data.get("password_hash", ""):
            st.session_state.authenticated = True
            st.session_state.username = username
            st.session_state.data_file = DATA_FILE
            st.session_state.data = login_data
            st.query_params["user"] = username
            st.success("ログインできたよ")
            st.rerun()
        else:
            st.error("合言葉が違うよ。")

st.markdown('</div>', unsafe_allow_html=True)

if not st.session_state.authenticated:
    st.stop()

DATA_FILE = st.session_state.data_file

# ---------- 初期化 ----------
if "data" not in st.session_state:
    st.session_state.data = load_data(DATA_FILE)

data = st.session_state.data
today = ensure_today_record(data)
save_data(data, DATA_FILE)

st.success(f"ログイン中: {st.session_state.username}")
if st.button("ログアウト"):
    st.session_state.authenticated = False
    if "data" in st.session_state:
        del st.session_state.data
    st.rerun()

now_japan = get_japan_now()
st.info(f"現在時刻（日本）: {now_japan.strftime('%Y年%m月%d日 %H:%M')}")

# ---------- 設定 ----------
st.subheader("⚙️ 設定")

with st.form("settings_form"):
    col1, col2 = st.columns(2)
    with col1:
        base_cigs = st.number_input(
            "元々1日に吸っていた本数",
            min_value=0,
            value=int(data.get("base_cigs_per_day", 20)),
            step=1,
        )
    with col2:
        target_cigs = st.number_input(
            "今の目標本数",
            min_value=0,
            value=int(data.get("target_cigs_per_day", 10)),
            step=1,
        )

    col3, col4 = st.columns(2)
    with col3:
        pack_price = st.number_input(
            "1箱の値段（円）",
            min_value=0,
            value=int(data.get("pack_price", 600)),
            step=10,
        )
    with col4:
        cigs_per_pack = st.number_input(
            "1箱の本数",
            min_value=1,
            value=int(data.get("cigs_per_pack", 20)),
            step=1,
        )

    submitted = st.form_submit_button("設定を保存")

if submitted:
    data["base_cigs_per_day"] = int(base_cigs)
    data["target_cigs_per_day"] = int(target_cigs)
    data["pack_price"] = int(pack_price)
    data["cigs_per_pack"] = int(cigs_per_pack)
    save_data(data, DATA_FILE)
    st.success("設定を保存したよ")
    st.rerun()

# ---------- 今日の状態 ----------
st.subheader("📅 今日の状態")
st.caption(f"今日の日付: {today}")

today_stats = calculate_day_stats(data, today)

col1, col2 = st.columns(2)
col1.metric("今日吸った本数", f"{today_stats['count']}本")
col2.metric("1本あたり", f"{today_stats['one_price']:.1f}円")

col3, col4 = st.columns(2)
col3.metric("今日使った金額", f"{today_stats['actual_cost']:.0f}円")
col4.metric("今日の節約額", f"{today_stats['saved']:.0f}円")

col5, col6 = st.columns(2)
col5.metric("目標まで残り", f"{today_stats['remaining']}本")
col6.metric("目標超過", f"{today_stats['over']}本")

if today_stats["count"] == 0:
    st.success("今日はまだ0本。めっちゃいいスタート。")
elif today_stats["over"] == 0:
    st.success("目標ペース内。かなりいい感じ。")
else:
    st.warning("目標を超えてる。次の1本を少し遅らせてみよう。")

# ---------- 累計 ----------
st.subheader("💰 継続の成果")
total_stats = calculate_total_stats(data)

st.markdown(
    f"""
<div class="big-card">
    <p>これまでに節約できた金額</p>
    <h1>{total_stats['total_saved']:.0f}円</h1>
    <p>累計 {total_stats['total_count']}本 / 使用額 {total_stats['total_cost']:.0f}円</p>
</div>
""",
    unsafe_allow_html=True,
)

# ---------- 操作 ----------
st.subheader("🕹️ 操作")

col1, col2, col3 = st.columns(3)

if col1.button("＋1本", use_container_width=True):
    set_count(data, today, today_stats["count"] + 1)
    save_data(data, DATA_FILE)
    st.rerun()

if col2.button("−1本", use_container_width=True):
    set_count(data, today, today_stats["count"] - 1)
    save_data(data, DATA_FILE)
    st.rerun()

if col3.button("今日を0本", use_container_width=True):
    set_count(data, today, 0)
    save_data(data, DATA_FILE)
    st.rerun()

manual_count = st.number_input(
    "今日の本数を直接入力",
    min_value=0,
    value=int(today_stats["count"]),
    step=1,
)

if st.button("本数を反映", use_container_width=True):
    set_count(data, today, manual_count)
    save_data(data, DATA_FILE)
    st.success("本数を更新したよ")
    st.rerun()

# ---------- 履歴とグラフ ----------
st.subheader("📈 履歴とグラフ")
df = make_history_df(data)

if not df.empty:
    show_df = df.copy()
    show_df["日付"] = show_df["日付"].dt.strftime("%Y-%m-%d")
    st.dataframe(show_df, use_container_width=True, hide_index=True)

    chart_df = df.set_index("日付")[["吸った本数", "節約額"]]
    st.line_chart(chart_df)
else:
    st.info("まだ履歴がないよ。今日から記録スタート。")

st.caption("ユーザー名と合言葉ごとに記録を分けて保存されるよ")
