# 二世のstreamlineのcolor mapを採用したもの

import os
import sys
import numpy as np
import nibabel as nib
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from dipy.io.streamline import load_tck
from dipy.viz import window, actor
from dipy.io.image import load_nifti
from dipy.tracking.streamline import transform_streamlines
from scipy.ndimage import gaussian_filter


# コマンドライン引数でディレクトリを取得
if len(sys.argv) < 2:
    print("使用方法: python FAmap_auto.py <参照フォルダ>")
    sys.exit(1)

# .tck ファイルと参照画像のパス
dir = sys.argv[1]

tck_file = os.path.join(dir, "track.tck")
reference_file = os.path.join(dir, "DWI.nii.gz")  # DWI 参照画像 #eddy補正なしの場合はこっちを使う
# reference_file = os.path.join(dir, "DWI_eddy_corrected.nii.gz")  # DWI 参照画像 #eddy補正アリの場合はこっちを使う(?)

# 追加：カメラを指定方向にセットする関数
def set_camera_view(scene, actor, view="front"):
    # 表示対象の中心と大きさから、適切なカメラ距離を決める
    xmin, xmax, ymin, ymax, zmin, zmax = actor.GetBounds()
    cx = 0.5 * (xmin + xmax)
    cy = 0.5 * (ymin + ymax)
    cz = 0.5 * (zmin + zmax)
    rx = (xmax - xmin)
    ry = (ymax - ymin)
    rz = (zmax - zmin)
    dist = 2.0 * max(rx, ry, rz)  # 画面に収まる程度の距離

    cam = scene.GetActiveCamera()

    if view == "front":          # Yマイナス方向から中心を見る（正面）
        cam.SetPosition(cx, cy + dist, cz)
        cam.SetFocalPoint(cx, cy, cz)
        cam.SetViewUp(0, 0, 1)
    elif view == "back":         # 背面
        cam.SetPosition(cx, cy - dist, cz)
        cam.SetFocalPoint(cx, cy, cz)
        cam.SetViewUp(0, 0, 1)
    elif view == "left":         # 左側面（Xマイナス）
        cam.SetPosition(cx - dist, cy, cz)
        cam.SetFocalPoint(cx, cy, cz)
        cam.SetViewUp(0, 0, 1)
    elif view == "right":        # 右側面（Xプラス）
        cam.SetPosition(cx + dist, cy, cz)
        cam.SetFocalPoint(cx, cy, cz)
        cam.SetViewUp(0, 0, 1)
    elif view == "top":          # 上面（Zプラス）
        cam.SetPosition(cx, cy, cz + dist)
        cam.SetFocalPoint(cx, cy, cz)
        cam.SetViewUp(0, 1, 0)
    elif view == "bottom":       # 下面（Zマイナス）
        cam.SetPosition(cx, cy, cz - dist)
        cam.SetFocalPoint(cx, cy, cz)
        cam.SetViewUp(0, 1, 0)
    else:
        raise ValueError(f"unknown view: {view}")

    scene.ResetCameraClippingRange()


# FAマップと DWI のロード
fa_data, fa_affine = load_nifti(os.path.join(dir, "Files_FA.nii.gz"))
dwi_data, dwi_affine = load_nifti(reference_file)

highlighted_fa_path = os.path.join(dir, "highlighted_FA.nii.gz")

# FAマップと DWI のロード

# .tck ファイルをロード
sft = load_tck(tck_file, reference=reference_file)
streamlines = sft.streamlines 

# DWI の座標系から FA マップの座標系への変換行列
affine_transform = np.linalg.inv(dwi_affine) @ fa_affine

# ストリームラインをFAマップの空間に変換
streamlines_transformed = list(transform_streamlines(streamlines, affine_transform))

# 各streamlineの平均FA値を格納
fa_means = []

for streamline in streamlines_transformed:
    fa_values = []

    for point in streamline:
        # 世界座標 → FAマップのボクセル座標（整数）
        voxel = np.round(np.dot(np.linalg.inv(fa_affine), np.append(point, 1))[:3]).astype(int)

        # ボクセルが範囲内ならFA値を追加
        if all((0 <= voxel) & (voxel < fa_data.shape)):
            fa_values.append(fa_data[tuple(voxel)])

    # 平均FA値を記録（通ったボクセルが1つもなければ0とする）
    if fa_values:
        fa_means.append(np.mean(fa_values))
    else:
        fa_means.append(0.0)

# FA値の最小・最大を取得（全streamlineを対象に正規化）
fa_min = np.min(fa_means)
fa_max = np.max(fa_means)

colormap = cm.get_cmap('jet_r')  # カラーマップ選択

def get_color(fa, fa_min, fa_max):
    norm = 0.0 if fa_max - fa_min == 0 else (fa - fa_min) / (fa_max - fa_min)
    return list(colormap(norm)[:3])  # RGBだけ取り出す

# streamlineごとの色を計算
streamline_colors = np.array([get_color(fa, fa_min, fa_max) for fa in fa_means])

stream_actor = actor.line(streamlines_transformed, colors=streamline_colors)
scene = window.Scene()
scene.add(stream_actor)

# ここで正面に固定
set_camera_view(scene, stream_actor, view="front")

window.show(scene)

# # 3D可視化
# stream_actor = actor.line(streamlines_transformed, colors=streamline_colors)
# scene = window.Scene()
# scene.add(stream_actor)
# window.show(scene)



