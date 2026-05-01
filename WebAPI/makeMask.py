import os
from pathlib import Path
import numpy as np
import nibabel as nib
import matplotlib.pyplot as plt
import streamlit as st
from PIL import Image
from streamlit_drawable_canvas import st_canvas


def _resize_bool_mask(mask_bool: np.ndarray, new_size: tuple[int, int]) -> np.ndarray:
    im = Image.fromarray(mask_bool.astype(np.uint8) * 255)
    im = im.resize(new_size, resample=Image.NEAREST)
    return (np.array(im) > 127)

# ---- 便利関数（2Dスライスの読み書き） ----
def get_slice(vol3d: np.ndarray, axis: str, idx: int) -> np.ndarray:
    if axis == "Axial":      sl = vol3d[:, :, idx]
    elif axis == "Coronal":  sl = vol3d[:, idx, :]
    else:                     sl = vol3d[idx, :, :]
    return np.rot90(sl)

def set_slice(vol3d: np.ndarray, axis: str, idx: int, sl_rot: np.ndarray) -> None:
    sl = np.rot90(sl_rot, k=3)
    if axis == "Axial":      vol3d[:, :, idx] = sl
    elif axis == "Coronal":  vol3d[:, idx, :] = sl
    else:                    vol3d[idx, :, :] = sl

def to_uint8(img2d: np.ndarray) -> np.ndarray:
    x = np.nan_to_num(img2d.astype(float))
    lo, hi = np.percentile(x, (1, 99))
    if not np.isfinite(lo): lo = 0.0
    if not np.isfinite(hi) or hi <= lo: hi = lo + 1.0
    x = (x - lo) / (hi - lo)
    x = np.clip(x, 0, 1)
    return (x * 255).astype(np.uint8)



def make_bg_image(dwi_sl: np.ndarray, roi_sl_bool: np.ndarray, alpha: float = 0.40) -> Image.Image:
    """DWI をグレースケール、ROI を赤で重ねた合成画像を作る"""
    base = to_uint8(dwi_sl)
    rgb = np.dstack([base, base, base]).copy()
    if roi_sl_bool is not None:
        m = roi_sl_bool.astype(bool)
        rgb[m, 0] = 255  # R
        # G,B はそのまま（うっすら赤く見える）
    return Image.fromarray(rgb)

def read_bvals(bval_path: Path) -> np.ndarray:
    """FSL形式の .bval を読み込んで 1D array を返す（空白/改行区切り対応）"""
    txt = Path(bval_path).read_text().strip()
    vals = [float(x) for x in txt.replace("\n", " ").split() if x.strip() != ""]
    return np.asarray(vals, dtype=float)

def find_b0_indices(bval_path: Path, threshold: float = 50.0) -> np.ndarray:
    """b<=threshold を b=0 とみなしてインデックス配列を返す"""
    if not bval_path.exists():
        return np.array([], dtype=int)
    bvals = read_bvals(bval_path)
    return np.where(bvals <= threshold)[0]

def load_nii_slice(path: Path, axis: str, slice_idx: int, vol_idx: int | None = None):
    """4D NIfTIは vol_idx で1ボリュームに絞ってからスライスを取り出す"""
    img = nib.load(str(path))
    data = img.get_fdata()

    # 4D -> 3D に落とす
    if data.ndim == 4:
        nvol = data.shape[3]
        vol_idx = 0 if vol_idx is None else int(np.clip(vol_idx, 0, nvol - 1))
        data3 = data[:, :, :, vol_idx]
    else:
        data3 = data

    # 軸ごとにスライス抽出
    if axis == "Axial":      # z
        slice_idx = int(np.clip(slice_idx, 0, data3.shape[2] - 1))
        sl = data3[:, :, slice_idx]
    elif axis == "Coronal":  # y
        slice_idx = int(np.clip(slice_idx, 0, data3.shape[1] - 1))
        sl = data3[:, slice_idx, :]
    else:                    # Sagittal -> x
        slice_idx = int(np.clip(slice_idx, 0, data3.shape[0] - 1))
        sl = data3[slice_idx, :, :]

    return np.rot90(sl)

def show_images(tmp_dir: str):
    dwi_path  = Path(tmp_dir) / "DWI.nii.gz"
    mask_path = Path(tmp_dir) / "output_mask.nii.gz"
    bval_path = Path(tmp_dir) / "DWI.bval"

    if not dwi_path.exists() or not mask_path.exists():
        st.warning("DWI または mask の出力が見つかりません。")
        return

    axis = st.radio("表示軸", ["Axial", "Coronal", "Sagittal"], horizontal=True)

    dwi_img = nib.load(str(dwi_path))
    dwi_shape = dwi_img.shape
    x, y, z = dwi_shape[:3]
    max_idx_map = {"Axial": z - 1, "Coronal": y - 1, "Sagittal": x - 1}
    idx = st.slider("スライス位置", 0, max_idx_map[axis], max_idx_map[axis] // 2, key=f"slice_{axis}")

    # b=0 自動選択
    vol_idx = 0
    if len(dwi_shape) == 4:
        b0_inds = find_b0_indices(bval_path, threshold=50.0)
        if b0_inds.size > 0:
            vol_idx = int(b0_inds[0])
            st.caption(f"b=0 自動選択: volume index = {vol_idx}（候補: {b0_inds.tolist()}）")
        else:
            st.caption("b=0 が見つからなかったため、volume 0 を表示しています。")

    dwi_sl  = load_nii_slice(dwi_path, axis, idx, vol_idx=vol_idx)  # 4D対応
    mask_sl = load_nii_slice(mask_path, axis, idx, vol_idx=None)    # maskは通常3D

    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("DWI")
        fig, ax = plt.subplots()
        ax.imshow(dwi_sl, cmap="gray"); ax.axis("off")
        st.pyplot(fig)
    with col2:
        st.subheader("Mask")
        fig, ax = plt.subplots()
        ax.imshow(mask_sl, cmap="gray"); ax.axis("off")
        st.pyplot(fig)
    with col3:
        st.subheader("Overlay")
        fig, ax = plt.subplots()
        ax.imshow(dwi_sl, cmap="gray")
        ax.imshow(mask_sl, cmap="jet", alpha=0.35)
        ax.axis("off")
        st.pyplot(fig)

def show_overlay_editor(
    tmp_dir: str,
    key_ns: str = "maskedit",
    canvas_target_px: int = 1200,   # ← 右側キャンバスの目標横幅（px）
    default_brush: int = 24
):

    sid = Path(tmp_dir).name
    ns  = f"{key_ns}_{sid}"

    # 追加：キャンバスを強制初期化するためのトークン
    tok_key = f"{ns}_clear_token"
    if tok_key not in st.session_state:
        st.session_state[tok_key] = 0

    def _clear_strokes():
        st.session_state[tok_key] += 1
        try:
            st.rerun()                 # Streamlit 1.32+ ならこちらが呼ばれる
        except Exception:
            st.experimental_rerun()    # 旧版互換


    dwi_path  = Path(tmp_dir) / "DWI.nii.gz"
    bval_path = Path(tmp_dir) / "DWI.bval"
    roi_path  = Path(tmp_dir) / "output_mask.nii.gz"

    if not dwi_path.exists() or not roi_path.exists():
        st.warning("DWI または output_mask.nii.gz が見つかりません。")
        return

    # ---- DWI 3D（b=0自動選択）をキャッシュ ----
    if f"{ns}_dwi3d" not in st.session_state:
        dwi_img  = nib.load(str(dwi_path))
        dwi_data = dwi_img.get_fdata()
        if dwi_data.ndim == 4:
            b0_inds = find_b0_indices(bval_path, threshold=50.0)
            vol_idx = int(b0_inds[0]) if b0_inds.size > 0 else 0
            dwi3d   = dwi_data[..., vol_idx]
        else:
            dwi3d   = dwi_data
        st.session_state[f"{ns}_dwi3d"] = dwi3d

    # ---- ROI 3D（編集対象）をキャッシュ ----
    if f"{ns}_roi3d" not in st.session_state:
        roi_img = nib.load(str(roi_path))
        st.session_state[f"{ns}_roi_affine"] = roi_img.affine
        st.session_state[f"{ns}_roi_hdr"]    = roi_img.header
        st.session_state[f"{ns}_roi3d"]      = roi_img.get_fdata().astype(np.float32)

    dwi3d = st.session_state[f"{ns}_dwi3d"]
    roi3d = st.session_state[f"{ns}_roi3d"]
    x, y, z = dwi3d.shape

    # ===== レイアウト：左（操作）／右（編集キャンバス 大）=====
    left, right = st.columns([3, 7], vertical_alignment="top")

    with left:
        axis = st.radio("軸", ["Axial", "Coronal", "Sagittal"],
                        key=f"{ns}_axis", horizontal=False)
        max_idx = {"Axial": z - 1, "Coronal": y - 1, "Sagittal": x - 1}[axis]
        idx = st.slider("スライス", 0, max_idx, max_idx // 2,
                        key=f"{ns}_slice")
        mode = st.radio("編集モード", ["追加", "削除", "オフ"],
                        index=0, key=f"{ns}_mode", horizontal=True)
        brush = st.slider("ブラシサイズ（px）", 2, 120, default_brush,
                        key=f"{ns}_brush")

        # 保存ボタン：ファイルへ書き出し＋筆跡クリア
        if st.button("ROIを保存（NIfTI上書き）", key=f"{ns}_save"):
            out = Path(tmp_dir) / "output_mask.nii.gz"
            roi_img = nib.Nifti1Image(
                (roi3d > 0.5).astype(np.uint8),
                st.session_state[f"{ns}_roi_affine"],
                st.session_state[f"{ns}_roi_hdr"]
            )
            nib.save(roi_img, str(out))
            st.success(f"保存しました: {out.name}")
            _clear_strokes()  # ← ここは必ずインデントされていること！

        # 手動クリアボタン
        if st.button("このスライスの手描きをクリア", key=f"{ns}_clear_btn"):
            _clear_strokes()  # ← ここもインデント



    with right:
        # 背景（Overlay）作成：プレビュー画像は表示しない
        dwi_sl = get_slice(dwi3d, axis, idx)
        roi_sl = (get_slice(roi3d, axis, idx) > 0.5)
        bg     = make_bg_image(dwi_sl, roi_sl)

        # コンテナ横幅に合わせたいときは canvas_target_px を上げ下げ
        scale  = max(1.0, canvas_target_px / bg.width)
        disp_w = int(bg.width * scale)
        disp_h = int(bg.height * scale)
        bg_disp = bg.resize((disp_w, disp_h), resample=Image.NEAREST)

        drawing_mode = "freedraw" if mode != "オフ" else "transform"  # ← Noneにしない
        canvas = st_canvas(
            fill_color="rgba(0,255,0,0.6)",
            stroke_color="#00FF00",
            stroke_width=brush,
            background_image=bg_disp,   # キャンバスは編集用のみ
            update_streamlit=True,
            height=disp_h,
            width=disp_w,
            drawing_mode=drawing_mode,
            key=f"{ns}_canvas",
        )

        # 描いた緑部分を抽出 → 元解像度に戻して ROI へ反映
        if mode != "オフ" and canvas.image_data is not None:
            img = canvas.image_data.astype(np.uint8)
            drawn_disp = (img[:, :, 1] > 200) & (img[:, :, 0] < 100) & (img[:, :, 2] < 100)
            if drawn_disp.any():
                drawn_orig = _resize_bool_mask(drawn_disp, (bg.width, bg.height))
                if mode == "追加":
                    new_sl = (roi_sl | drawn_orig).astype(np.uint8)
                else:
                    new_sl = (roi_sl & (~drawn_orig)).astype(np.uint8)
                set_slice(roi3d, axis, idx, new_sl)
                st.session_state[f"{ns}_roi3d"] = roi3d
                st.toast(f"{axis} スライス {idx} を更新", icon="✅")

