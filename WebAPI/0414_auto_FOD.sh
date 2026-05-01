#!/bin/bash
# マスク画像は、全部白
# FODを使ったtractography処理
# スクリプトをエラー時に停止

set -e  # エラーが発生したらスクリプトを終了
trap 'echo "エラーが発生しました。処理を中断します。" >&2; exit 1' ERR

source /Users/rira/Documents/研究室/卒業研究/MRtrix3/.mrtrixenv/bin/activate
# 引数の確認
if [[ $# -lt 1 ]]; then
  echo "使用方法: $0 <DICOMフォルダ> <出力フォルダ>"
  exit 1
fi

DICOM_DIR=$(realpath "$1")
OUTPUT_DIR=$2

# DICOMフォルダの存在確認
if [[ ! -d "$DICOM_DIR" ]]; then
  echo "指定されたDICOMフォルダが存在しません: $DICOM_DIR"
  exit 1
fi

# 出力フォルダの確認・作成
if [[ -d "$OUTPUT_DIR" ]]; then
  OUTPUT_DIR=$(realpath "$OUTPUT_DIR")
  echo "指定された出力フォルダは既に存在します: $OUTPUT_DIR"
  echo -n "上書きしてもよろしいですか？ (y/n): "
  read CONFIRMATION
  if [[ "$CONFIRMATION" == "y" ]]; then
    echo "フォルダ内のファイルを削除します..."
    rm -rf "$OUTPUT_DIR"/*  # フォルダ内のすべてのファイルを削除
  else
    echo "処理を中止しました。"
    exit 0
  fi
  
else
  echo "出力フォルダを作成します: $OUTPUT_DIR"
  mkdir -p "$OUTPUT_DIR"
  OUTPUT_DIR=$(realpath "$OUTPUT_DIR")
fi

# 1. DICOMの変換を実行
echo "Step1:DICOMファイルをNIFTIに変換中..."
dcm2niix -o "$OUTPUT_DIR" -f "DWI" -b y -z y "$DICOM_DIR"

# 出力フォルダ
NIFTI_FILE=$(realpath "$OUTPUT_DIR/DWI.nii.gz")
BVEC_FILE=$(realpath "$OUTPUT_DIR/DWI.bvec")
BVAL_FILE=$(realpath "$OUTPUT_DIR/DWI.bval")
JSON_FILE=$(realpath "$OUTPUT_DIR/DWI.json")


# mask予測のために、仮想環境を移動
deactivate
source /Users/rira/Documents/研究室/卒業研究/MRtrix3/.smpenv/bin/activate

# 深層学習を用いてNiftiからmask領域を推定
echo "深層学習を用いてNiftiからmask領域を推定中..."
python predict_nif.py "$OUTPUT_DIR"

# 仮想環境を戻す
deactivate
source /Users/rira/Documents/研究室/卒業研究/MRtrix3/.mrtrixenv/bin/activate

ROI_FILE=$(realpath "$OUTPUT_DIR/output_mask.nii.gz")

# # 処理の開始
cd "$OUTPUT_DIR"

# 2. DWI データを MIF フォーマットに変換
echo "Step 2: Converting DWI data to MIF format..."
if ! mrconvert -fslgrad "$BVEC_FILE" "$BVAL_FILE" -json_import "$JSON_FILE" "$NIFTI_FILE" DWI.mif; then
  echo "Error: mrconvert failed."
  exit 1
fi

# 3. DWI データのノイズ除去
dwidenoise DWI.mif DWI_denoised.mif


# 3. マスク画像の作成
echo "Step 3: Making white mask image (all voxels = 1)..."

if ! mrcalc DWI.mif 0 -eq - | mrcalc - 1 -add DWI_mask.mif; then
  echo "Error: mrcalc white mask failed."
  exit 1
fi

# 4. 白質応答関数の計算
echo "Step 4: Calculating WM response function..."
if ! dwi2response tournier DWI.mif WM_response_function.tx; then
  echo "Error: dwi2response failed."
  exit 1
fi

# 5. FOD (Fiber Orientation Distribution) の生成
echo "Step 5: Generating FOD (Fiber Orientation Distribution)..."
if ! dwi2fod csd DWI.mif WM_response_function.tx WM_FOD.mif -mask DWI_mask.mif; then
  echo "Error: dwi2fod failed."
  exit 1
fi

# 6. トラクトグラフィーの生成
echo "Step 6: Generating tractography..."
if ! tckgen WM_FOD.mif track.tck -seed_image "$ROI_FILE" -mask DWI_mask.mif -select 20000 -minlength 10; then
  echo "Error: tckgen failed."
  exit 1
fi

cd "$OUTPUT_DIR"

mrconvert DWI_mask.mif DWI_mask.nii.gz

dtifit -k DWI.nii.gz -o Files -m DWI_mask.nii.gz -r DWI.bvec -b DWI.bval

cd /Users/rira/Documents/研究室/卒業研究/MRtrix3   

echo "trcファイルの作成が完了しました。仮想環境を移動します"

# 仮想環境1を終了
deactivate || echo "仮想環境1の終了に問題がありましたが、処理を続行します。"

echo "次の仮想環境を有効化します..."
source /Users/rira/Documents/研究室/卒業研究/MRtrix3/.tractenv3/bin/activate

# 仮想環境の有効化確認
if [[ "$VIRTUAL_ENV" != "/Users/rira/Documents/研究室/卒業研究/MRtrix3/.tractenv3" ]]; then
  echo "仮想環境の有効化に失敗しました。"
  exit 1
fi

echo "仮想環境2内で処理を実行します..."
if ! python FAmap_auto.py $OUTPUT_DIR; then
  echo "Error: FAmap_auto_.py の実行に失敗しました。"
  exit 1
fi



echo "仮想環境2での処理が正常に完了しました。"

echo "不要なファイルを削除します（必要なファイルは残します）..."

cd "$OUTPUT_DIR"

# 残したいファイルのリスト
keep_files=("track.tck" "Files_FA.nii.gz" "highlighted_FA.nii.gz" "DWI.nii.gz" "output_mask.nii.gz")

# すべてのファイルをループ
for file in *; do
  skip=false
  for keep in "${keep_files[@]}"; do
    if [[ "$file" == "$keep" ]]; then
      skip=true
      break
    fi
  done
  if [[ "$skip" == false ]]; then
    echo "削除: $file"
    rm -rf "$file"
  fi
done

echo "必要なファイルを残して削除処理を完了しました。"


# 仮想環境2を終了
deactivate || echo "仮想環境2の終了に問題がありましたが、処理を続行します。"

echo "すべての処理が正常に完了しました。"