import base64
import hashlib
import hmac
import io
import json
import os
import time
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError
from google import genai
from google.genai import types
from dotenv import load_dotenv
from PIL import Image


def format_date(value):
    if pd.isna(value) or not str(value).strip():
        return ""

    date_text = str(value).strip()
    for separator in (".", "/", " ", "　"):
        date_text = date_text.replace(separator, "-")
    parts = date_text.split("-")
    if len(parts) != 3:
        return str(value)

    try:
        year, month, day = map(int, parts)
        if year < 100:
            year += 2018
        return date(year, month, day).strftime("%Y/%m/%d")
    except (TypeError, ValueError):
        return str(value)


def format_amount(value):
    if pd.isna(value) or not str(value).strip():
        return ""

    amount = pd.to_numeric(
        str(value).replace("¥", "").replace(",", "").strip(),
        errors="coerce",
    )
    if pd.isna(amount):
        raise ValueError(f"金額が数値ではありません: {value!r}")
    if float(amount).is_integer():
        amount = int(amount)
    return f"{amount:,}"


load_dotenv(Path(__file__).with_name(".env"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


st.set_page_config(
    page_title="AI通帳コンバータ",
    page_icon="🏦",
    layout="wide",
)

try:
    APP_PASSWORD = st.secrets["APP_PASSWORD"]
except (KeyError, StreamlitSecretNotFoundError):
    st.error(
        "アプリの認証設定がありません。"
        " secrets.toml に APP_PASSWORD を設定してください。"
    )
    st.stop()

if not isinstance(APP_PASSWORD, str) or not APP_PASSWORD:
    st.error("APP_PASSWORD に空でない文字列を設定してください。")
    st.stop()

if not st.session_state.get("logged_in", False):
    st.markdown(
        """
        <style>
        .auth-header {
            padding: 1rem 0 0.5rem;
            text-align: center;
        }
        .auth-header .brand-mark {
            display: inline-flex;
            width: 3.5rem;
            height: 3.5rem;
            align-items: center;
            justify-content: center;
            margin-bottom: 0.75rem;
            border: 1px solid #dce8f7;
            border-radius: 1.15rem;
            background: #ffffff;
            box-shadow: 0 8px 24px rgba(28, 76, 130, 0.1);
            font-size: 1.8rem;
        }
        .auth-header h1 {
            margin: 0;
            color: #142b4a;
            font-size: 2rem;
        }
        .auth-header p {
            margin: 0.65rem 0 1rem;
            color: #718198;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    _, login_column, _ = st.columns([1, 1.2, 1])
    with login_column:
        with st.container(border=True):
            st.markdown(
                """
                <div class="auth-header">
                    <div class="brand-mark">🏦</div>
                    <h1>AI通帳コンバータ</h1>
                    <p>続行するにはパスワードを入力してください。</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            password_input = st.text_input(
                "パスワード",
                type="password",
                key="auth_password",
            )
            if st.button("ログイン", type="primary", use_container_width=True):
                if hmac.compare_digest(
                    password_input.encode("utf-8"),
                    APP_PASSWORD.encode("utf-8"),
                ):
                    st.session_state["logged_in"] = True
                    st.rerun()
                else:
                    st.error("パスワードが正しくありません。")
    st.stop()

st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(145deg, #f5f8fc 0%, #edf3fa 100%);
        color: #172b4d;
    }
    .block-container {
        max-width: 1240px;
        padding-top: 2.5rem;
        padding-bottom: 4rem;
    }
    .app-header {
        margin: 0 auto 2rem;
        text-align: center;
    }
    .app-header .brand-mark {
        display: inline-flex;
        width: 3.5rem;
        height: 3.5rem;
        align-items: center;
        justify-content: center;
        margin-bottom: 0.75rem;
        border: 1px solid #dce8f7;
        border-radius: 1.15rem;
        background: #ffffff;
        box-shadow: 0 8px 24px rgba(28, 76, 130, 0.1);
        font-size: 1.8rem;
    }
    .app-header h1 {
        margin: 0;
        color: #142b4a;
        font-size: clamp(2rem, 4vw, 2.8rem);
        font-weight: 750;
        letter-spacing: -0.045em;
    }
    .app-header p {
        margin: 0.65rem 0 0;
        color: #718198;
        font-size: 1rem;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border: 1px solid #e3eaf3;
        border-radius: 1rem;
        background: rgba(255, 255, 255, 0.94);
        box-shadow: 0 12px 32px rgba(30, 64, 105, 0.07);
    }
    .upload-intro {
        margin-bottom: 1rem;
        color: #718198;
        line-height: 1.7;
    }
    .stFileUploader section {
        border: 1px dashed #b7c9df;
        border-radius: 0.8rem;
        background: #f8fbff;
    }
    .stButton > button {
        min-height: 3rem;
        border: 0;
        border-radius: 0.75rem;
        background: linear-gradient(100deg, #2563eb 0%, #06b6d4 100%);
        color: #ffffff;
        font-weight: 650;
        box-shadow: 0 8px 18px rgba(37, 99, 235, 0.2);
        transition: transform 160ms ease, box-shadow 160ms ease, filter 160ms ease;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        border-color: transparent;
        color: #ffffff;
        box-shadow: 0 12px 24px rgba(37, 99, 235, 0.28);
        filter: brightness(1.04);
    }
    .stButton > button:focus:not(:active) {
        border-color: #60a5fa;
        color: #ffffff;
        box-shadow: 0 0 0 0.2rem rgba(59, 130, 246, 0.2);
    }
    section[data-testid="stSidebar"] {
        border-right: 1px solid #e3eaf3;
        background: #f9fbfe;
    }
    [data-testid="stDataFrame"] {
        border: 1px solid #e3eaf3;
        border-radius: 0.75rem;
        overflow: hidden;
    }
    @media (max-width: 640px) {
        .block-container {
            padding: 1.5rem 1rem 3rem;
        }
    }
    </style>
    <div class="app-header">
        <div class="brand-mark">🏦</div>
        <h1>通帳取引データ変換</h1>
        <p>複数の通帳画像をまとめて読み取り、弥生会計用CSVを作成します。</p>
    </div>
    """,
    unsafe_allow_html=True,
)

model_options = [
    "gemini-3.7-flash",
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-4-argon",
]
selected_model = st.sidebar.selectbox(
    "使用するAIモデル",
    model_options,
    index=0,
    help="画像の読み取りに使用するAIモデルを選択します。",
)

with st.container(border=True):
    st.markdown(
        '<div class="upload-intro">画像をアップロードして「読み取りを開始」を押してください。'
        " 読み取り後、取引内容を確認してCSVをダウンロードできます。</div>",
        unsafe_allow_html=True,
    )
    uploaded_files = st.file_uploader(
        "通帳画像",
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True,
        help="PNGまたはJPEG画像を複数選択できます。",
    )
    if uploaded_files:
        st.caption(f"{len(uploaded_files)}枚の画像を選択中")
    start_processing = st.button(
        "読み取りを開始", type="primary", use_container_width=True
    )

if (
    "bankbook_result" in st.session_state
    and st.session_state.get("bankbook_result_model") != selected_model
):
    st.session_state.pop("bankbook_result", None)
    st.session_state.pop("bankbook_result_image_hash", None)
    st.session_state.pop("bankbook_result_model", None)

uploaded_image_hash = hashlib.sha256(
    json.dumps(
        [
            hashlib.sha256(uploaded_file.getvalue()).hexdigest()
            for uploaded_file in uploaded_files
        ]
    ).encode("utf-8")
).hexdigest()
if (
    "bankbook_result" in st.session_state
    and st.session_state.get("bankbook_result_image_hash") != uploaded_image_hash
):
    st.session_state.pop("bankbook_result", None)
    st.session_state.pop("bankbook_result_image_hash", None)
    st.session_state.pop("bankbook_result_model", None)

if start_processing:
    st.session_state.pop("bankbook_result", None)
    st.session_state.pop("bankbook_result_image_hash", None)
    st.session_state.pop("bankbook_result_model", None)
    if not uploaded_files:
        st.error("先に通帳画像をアップロードしてください。")
    elif not GEMINI_API_KEY:
        st.error(".env に GEMINI_API_KEY が設定されていません。")
    else:
        prompt = (
            "この通帳の画像を読み取り、以下のキーを持つJSON配列（リスト形式）のみを出力してください。"
            "マークダウンブロック（```json）や余計なテキストは一切含めないでください。\n"
            '必須キー: "日付", "内容", "出金金額(円)", "入金金額(円)", "残高(円)"'
        )
        required_columns = [
            "日付",
            "内容",
            "出金金額(円)",
            "入金金額(円)",
            "残高(円)",
        ]
        image_results = []
        current_image_number = 0
        progress = st.progress(0, text="画像の処理を開始します...")
        try:
            client = genai.Client(
                api_key=GEMINI_API_KEY,
                http_options=types.HttpOptions(
                    timeout=120_000,
                    retry_options=types.HttpRetryOptions(attempts=1),
                ),
            )
            for current_image_number, uploaded_file in enumerate(
                uploaded_files, start=1
            ):
                progress.progress(
                    (current_image_number - 1) / len(uploaded_files),
                    text=f"全{len(uploaded_files)}枚中 {current_image_number}枚目を処理中...",
                )
                with st.spinner(
                    f"{current_image_number}枚目の画像を解析中です（最大2分）..."
                ):
                    image = Image.open(
                        io.BytesIO(uploaded_file.getvalue())
                    ).convert("RGB")
                    image_buffer = io.BytesIO()
                    image.save(image_buffer, format="PNG")
                    for retry_count in range(4):
                        try:
                            interaction = client.interactions.create(
                                model=selected_model,
                                input=[
                                    {"type": "text", "text": prompt},
                                    {
                                        "type": "image",
                                        "data": base64.b64encode(
                                            image_buffer.getvalue()
                                        ).decode("utf-8"),
                                        "mime_type": "image/png",
                                    },
                                ],
                                store=False,
                            )
                            break
                        except Exception as error:
                            status_code = getattr(error, "status_code", None)
                            if status_code is None:
                                status_code = getattr(error, "code", None)
                            if status_code is None:
                                response = getattr(error, "response", None)
                                status_code = getattr(response, "status_code", None)
                            try:
                                status_code = int(status_code)
                            except (TypeError, ValueError):
                                status_code = None
                            exception_names = {
                                cls.__name__.lower() for cls in type(error).__mro__
                            }
                            is_transient = status_code in {
                                429,
                                500,
                                502,
                                503,
                                504,
                            } or isinstance(
                                error, (TimeoutError, ConnectionError)
                            ) or any(
                                "timeout" in name or "connection" in name
                                for name in exception_names
                            )
                            if not is_transient or retry_count == 3:
                                raise
                            delay = 2 ** (retry_count + 1)
                            st.info(
                                f"サーバー混雑のため、{delay}秒後に再試行します..."
                            )
                            time.sleep(delay)

                parsed_data = json.loads(interaction.output_text)
                if not isinstance(parsed_data, list) or any(
                    not isinstance(row, dict) for row in parsed_data
                ):
                    raise ValueError(
                        "Geminiの応答がJSONオブジェクトの配列ではありません。"
                    )
                if any(
                    column not in row
                    for row in parsed_data
                    for column in required_columns
                ):
                    raise ValueError("Geminiの応答に必須キーが不足しています。")

                image_result = pd.DataFrame(
                    parsed_data, columns=required_columns
                )
                image_result["日付"] = (
                    image_result["日付"].replace("", pd.NA).ffill()
                )
                image_results.append(image_result)

            result = pd.concat(image_results, ignore_index=True)
            result["メモ"] = "-"
            result = result.loc[
                ~result["内容"].astype("string").str.contains("繰越", na=False)
            ].reset_index(drop=True)

            csv_columns = [
                "日付",
                "内容",
                "出金金額(円)",
                "入金金額(円)",
                "残高(円)",
                "メモ",
            ]
            result = result[csv_columns].copy()
            amount_columns = ["出金金額(円)", "入金金額(円)"]
            empty_amounts = result[amount_columns].apply(
                lambda column: column.isna()
                | column.astype("string").str.strip().eq("")
            )
            result = result.loc[~empty_amounts.all(axis=1)].copy()
            result["日付"] = result["日付"].map(format_date)
            for amount_column in [*amount_columns, "残高(円)"]:
                result[amount_column] = result[amount_column].map(format_amount)

            st.session_state["bankbook_result"] = result
            st.session_state["bankbook_result_image_hash"] = uploaded_image_hash
            st.session_state["bankbook_result_model"] = selected_model
            progress.progress(1.0, text="画像の読み取りと結合が完了しました")
            st.success("全ての読み取りと結合が完了しました！")
        except json.JSONDecodeError as error:
            st.error(
                f"{current_image_number}枚目のGemini応答をJSONとして"
                f"解析できませんでした: {error}"
            )
        except Exception as error:
            st.error(
                f"{current_image_number}枚目の通帳画像の読み取りに"
                f"失敗しました: {error}"
            )

if "bankbook_result" in st.session_state:
    result = st.session_state["bankbook_result"]
    with st.container(border=True):
        st.subheader("読み取り結果")
        st.caption(f"{len(result)}件の取引を表示しています")
        st.dataframe(result, use_container_width=True, hide_index=True)

        csv_buffer = io.BytesIO()
        result.to_csv(
            csv_buffer,
            index=False,
            header=False,
            encoding="cp932",
            errors="replace",
        )
        csv_bytes = csv_buffer.getvalue()
        default_file_name = "yayoi_kaikei"
        file_name = st.text_input(
            "ダウンロードするファイル名（.csvは不要）",
            value=default_file_name,
            key="csv_download_file_name",
        ).strip() or default_file_name
        download_file_name = f"{file_name}.csv"
        st.download_button(
            "弥生会計用CSVをダウンロード",
            data=csv_bytes,
            file_name=download_file_name,
            mime="text/csv",
        )