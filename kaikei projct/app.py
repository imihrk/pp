import pandas as pd
import streamlit as st


st.set_page_config(page_title="通帳自動データ化ツール（弥生会計用）")
st.title("通帳自動データ化ツール（弥生会計用）")
st.caption("画像読み取りは未対応のプロトタイプです。アップロード後、サンプルデータで変換を確認できます。")

uploaded_file = st.file_uploader(
    "通帳の画像またはPDFをアップロード",
    type=["png", "jpg", "jpeg", "pdf"],
)

if st.button("データ化を実行", disabled=uploaded_file is None):
    sample_data = [
        ["2026/04/01", "前月繰越", 0, 0, 125000],
        ["", "給与振込", 0, 250000, 375000],
        ["", "家賃", 80000, 0, 295000],
        ["2026/04/05", "電気料金", 12000, 0, 283000],
        ["", "ATM出金", 20000, 0, 263000],
    ]
    result = pd.DataFrame(
        sample_data,
        columns=["日付", "摘要", "出金金額", "入金金額", "残高"],
    )
    result["日付"] = result["日付"].replace("", pd.NA).ffill()
    st.session_state["bankbook_result"] = result

if "bankbook_result" in st.session_state:
    result = st.session_state["bankbook_result"]
    st.subheader("変換結果")
    st.dataframe(result, use_container_width=True, hide_index=True)

    csv_bytes = result.to_csv(index=False).encode("cp932")
    st.download_button(
        "弥生会計用CSVをダウンロード",
        data=csv_bytes,
        file_name="yayoi_import.csv",
        mime="text/csv",
    )