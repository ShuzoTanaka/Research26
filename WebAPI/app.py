import streamlit as st
import streamlit.components.v1 as components
import shutil
from dicom_reader import DICOMReader
import pandas as pd
import subprocess, tempfile, os, io, zipfile
from pathlib import Path
import nibabel as nib
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from makeMask import show_overlay_editor


st.title("FA Tractography Viewer")

st.set_page_config(
    page_title="FA Tractography Viewer",
    layout="wide",                     # ← ワイドレイアウトに
    initial_sidebar_state="collapsed"  # ← サイドバーを閉じて横幅を確保（任意）
)

# ビューポートの 85% までコンテナを広げる（= 画面の8〜9割）
st.markdown("""
    <style>
/* コンテナ幅と左右の余白、そしてヘッダー高さを考慮した上側余白 */
.stAppViewContainer .main .block-container {
  max-width: min(85vw, 1600px);
  padding-top: 5rem;      /* ←ココを増やす（4〜6remで調整） */
  padding-left: 2rem;
  padding-right: 2rem;
}

/* タイトルは折り返し+見切れ防止 */
h1, .stMarkdown h1 {
  margin: 0 0 1rem 0;
  line-height: 1.25;
  white-space: normal !important;
  overflow-wrap: anywhere !important;
  word-break: break-word !important;
}

/* 横スクロール許可（長いタイトルがはみ出す場合の保険） */
html, body, .stApp { overflow-x: auto; }
</style>
""", unsafe_allow_html=True)

# ---- セッション状態の初期化 ----
for key, default in [
    ("folder", None),
    ("info_df", None),
    ("tmp_dir", None),
    ("upload_tmp_dir", None),
    ("_uploaded_names", None),
    ("started_analysis", False),
    ("analysis_done", False),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ---- DICOMフォルダアップロード ----
# webkitdirectory を input[type=file] に付与してフォルダ選択を有効化
components.html("""
<script>
(function() {
    function patchInputs() {
        try {
            var inputs = window.parent.document.querySelectorAll('input[type="file"]');
            inputs.forEach(function(el) {
                el.setAttribute('webkitdirectory', '');
                el.setAttribute('mozdirectory', '');
                el.removeAttribute('accept');
            });
        } catch(e) {}
    }
    patchInputs();
    [200, 500, 1000, 2000, 4000].forEach(function(d) { setTimeout(patchInputs, d); });
    try {
        new MutationObserver(patchInputs).observe(
            window.parent.document.body,
            { childList: true, subtree: true }
        );
    } catch(e) {}
})();
</script>
""", height=0)

uploaded_files = st.file_uploader(
    "DICOMフォルダを選択",
    accept_multiple_files=True,
    help="フォルダを丸ごと選択してください（中のファイルが自動的にアップロードされます）",
)

if uploaded_files:
    new_names = sorted(f.name for f in uploaded_files)
    if st.session_state._uploaded_names != new_names:
        # ファイルが変わったら古い一時ディレクトリを削除して作り直す
        if st.session_state.upload_tmp_dir:
            shutil.rmtree(st.session_state.upload_tmp_dir, ignore_errors=True)
        upload_dir = tempfile.mkdtemp(prefix="dicom_upload_")
        st.session_state.upload_tmp_dir = upload_dir
        for f in uploaded_files:
            # webkitdirectory では f.name が "フォルダ名/ファイル名" になる場合があるため
            # basename のみ取り出してフラットに保存する
            fname = Path(f.name).name
            (Path(upload_dir) / fname).write_bytes(f.read())
        st.session_state._uploaded_names = new_names
        st.session_state.folder = upload_dir
        reader = DICOMReader(upload_dir)
        info = reader.get_basic_info()
        df = pd.DataFrame.from_dict(info, orient="index", columns=["値"])
        df.index.name = "項目"
        df["値"] = df["値"].astype("string")
        st.session_state.info_df = df
        st.session_state.analysis_done = False

# 表示（選択結果 & DICOM情報）
if st.session_state.folder:
    st.success(f"選択されたフォルダ: {st.session_state.folder}")
if st.session_state.info_df is not None:
    st.table(st.session_state.info_df)

# 解析開始
if st.session_state.folder and st.button("解析を開始", key="start_btn"):
    # 一時出力先（/tmp 等）をセッションごとに作る
    if not st.session_state.tmp_dir:
        st.session_state.tmp_dir = tempfile.mkdtemp(prefix="faapp_")
    tmp_dir = st.session_state.tmp_dir

    with st.spinner(f"解析を開始します（出力先: {tmp_dir}）…"):
        try:
            result = subprocess.run(
                ["python", "process1.py", st.session_state.folder, tmp_dir],
                capture_output=True, text=True, check=True
            )
            st.session_state.analysis_done = True
            st.success("解析が完了しました。")
            with st.expander("ログを表示"):
                st.code(result.stdout or "", language="bash")
                if result.stderr:
                    st.code(result.stderr, language="bash")
        except subprocess.CalledProcessError as e:
            st.session_state.analysis_done = False
            st.error("解析中にエラーが発生しました。")
            st.code(e.stdout or "", language="bash")
            st.code(e.stderr or "", language="bash")
            
def run_and_stream_with_marker(cmd, marker="===FOD_TRACT_CORE_DONE==="):
    with st.expander("解析ログ（後半）", expanded=True):
        log_ph = st.empty()
        status_ph = st.empty()
        buf = io.StringIO()

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        core_done_shown = False
        for line in proc.stdout:
            print(line, end="")        # ターミナルにも出す
            buf.write(line)
            log_ph.code(buf.getvalue(), language="bash")

            if (not core_done_shown) and (marker in line):
                core_done_shown = True
                st.session_state["tract_core_done"] = True
                status_ph.success("FOD/Tractography が完了しました。可視化を起動しました。")

        ret = proc.wait()
        return ret, buf.getvalue()

# 解析完了後の表示部
if st.session_state.analysis_done and st.session_state.tmp_dir:
    # overlayのみ表示＋ROIの追加/削除ができる
    # show_overlay_editor(st.session_state.tmp_dir, key_ns="mask_main")

    if st.button("解析スタート（FOD/Tractography）", key="tract_btn"):
        outdir = st.session_state.tmp_dir
        with st.spinner("FOD/Tractography を実行中…"):
            ret2, log2 = run_and_stream_with_marker(["bash", "process2.sh", outdir])
            if ret2 == 0:
                # ここで二重に success を出す必要はなし（マーカーで既に表示済み）
                st.info("後半処理プロセスは完了しました。（可視化ウィンドウは別プロセスで起動中）")
            else:
                st.error(f"後半解析が失敗しました（終了コード: {ret2}）")




# ---- 保存（ZIP ダウンロード）＆ クリーンアップ ----
def zip_outputs(dir_path: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(dir_path):
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, dir_path)
                zf.write(full, arcname=rel)
    buf.seek(0)
    return buf.read()

if st.session_state.analysis_done and st.session_state.tmp_dir:
    st.divider()
    col_dl, col_rm = st.columns(2)
    with col_dl:
        if st.download_button(
            "結果を保存（ZIP）",
            data=zip_outputs(st.session_state.tmp_dir),
            file_name="fa_results.zip"
        ):
            st.success("ダウンロードを開始しました。")
    with col_rm:
        if st.button("一時フォルダを削除"):
            import shutil
            shutil.rmtree(st.session_state.tmp_dir, ignore_errors=True)
            st.session_state.tmp_dir = None
            st.session_state.analysis_done = False
            st.info("一時フォルダを削除しました。")
