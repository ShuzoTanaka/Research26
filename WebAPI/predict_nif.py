import os
import sys
from pathlib import Path
import numpy as np
import nibabel as nib
import cv2
import torch
import segmentation_models_pytorch as smp
from tqdm import tqdm

# コマンドライン引数でディレクトリを取得
if len(sys.argv) < 2:
    print("使用方法: python tract.py <ディレクトリパス>")
    sys.exit(1)

directory_path = sys.argv[1]
nifti_path = os.path.join(directory_path, "DWI.nii.gz")
if not os.path.isfile(nifti_path):
    print(f"NIfTIファイルが見つかりません: {nifti_path}")
    sys.exit(1)
output_nifti_path = os.path.join(directory_path, "output_mask.nii.gz")
image_folder = os.path.join(directory_path, "image_folder")
output_folder = os.path.join(directory_path, "output_folder")

os.makedirs(image_folder, exist_ok=True)
os.makedirs(output_folder, exist_ok=True)

# ====== 1. NIfTIの読み込みとPNGスライス保存 ======
# NIfTI読み込み
nii = nib.load(nifti_path)
volume = nii.get_fdata()  # shape: (256, 256, 52, 12)
affine = nii.affine

# 最初のチャンネル（4次元目の index 0）を使用
for i in range(volume.shape[2]):
    slice_img = volume[:, :, i, 0]  # shape: (256, 256)
    norm_img = (
        (slice_img - slice_img.min()) / (np.ptp(slice_img) + 1e-8) * 255
    ).astype(np.uint8)
    cv2.imwrite(os.path.join(image_folder, f"slice_{i:03}.png"), norm_img)


# ====== 2. モデル読み込みと前処理 ======
ENCODER = "resnet34"
ENCODER_WEIGHTS = "imagenet"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
_MODEL_PATH = Path(__file__).parent / "20250623_2058_unet_resnet34.pth"
model = torch.load(
    str(_MODEL_PATH),
    map_location=DEVICE,
    weights_only=False,
)
model.eval()

preprocessing_fn = smp.encoders.get_preprocessing_fn(ENCODER, ENCODER_WEIGHTS)


def preprocess_image(path):
    image = cv2.imread(path)
    image = cv2.resize(image, (256, 256))
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    image = preprocessing_fn(image)
    image = image.transpose(2, 0, 1).astype("float32")
    return torch.from_numpy(image).unsqueeze(0)


# ====== 3. PNG → 推論 → マスク保存 ======
png_files = sorted(os.listdir(image_folder))
for f in tqdm(png_files):
    path = os.path.join(image_folder, f)
    x_tensor = preprocess_image(path).to(DEVICE)
    with torch.no_grad():
        pred = model(x_tensor)
    mask = pred.squeeze().cpu().numpy()
    mask = np.argmax(mask, axis=0).astype(np.uint8)  # 0,1,2クラス
    cv2.imwrite(os.path.join(output_folder, f), mask * 127)  # 可視化用に127, 255など

# ====== 4. 推論マスクをNIfTI形式に再構成 ======
mask_slices = []
for f in sorted(os.listdir(output_folder)):
    m = cv2.imread(os.path.join(output_folder, f), cv2.IMREAD_GRAYSCALE)
    mask_slices.append(m // 127)  # 元のクラス0/1/2に戻す

mask_volume = np.stack(mask_slices, axis=-1).astype(np.uint8)
nifti_mask = nib.Nifti1Image(mask_volume, affine)

data = nifti_mask.get_fdata()
    
# ラベル1（画素値255）のみを抽出
extracted_data = np.where(data == 1, 1, 0)

# 新しいNIfTI画像を作成
new_nifti_img = nib.Nifti1Image(extracted_data, affine=nifti_mask.affine, header=nifti_mask.header)

# 出力ディレクトリの作成
output_dir = os.path.dirname(output_nifti_path)
os.makedirs(output_dir, exist_ok=True)

# 出力NIfTIファイルを保存
nib.save(new_nifti_img, output_nifti_path)
