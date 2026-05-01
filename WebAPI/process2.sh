#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# venv パス (ネイティブ環境用。Docker では各ツールが PATH 上に存在する)
MRTRIX_VENV="${SCRIPT_DIR}/.mrtrixenv/bin/activate"
TRACT_VENV="${SCRIPT_DIR}/.tractenv3/bin/activate"
TRACT_VENV_PY="${SCRIPT_DIR}/.tractenv3/bin/python"

# tractenv3 の python が存在すればそれを、なければ PATH 上の python3/python を使用
if [ -f "$TRACT_VENV_PY" ]; then
    TRACT_PY="$TRACT_VENV_PY"
else
    TRACT_PY="$(command -v python3 || command -v python)"
fi

# 引数
OUTPUT_DIR="$1"
ROI_FILE="$OUTPUT_DIR/output_mask.nii.gz"

# 1) MRtrix 環境を有効化（ネイティブ環境のみ。Docker では MRtrix3 が PATH 上に存在）
if [ -f "$MRTRIX_VENV" ]; then
    source "$MRTRIX_VENV"
fi


cd "$OUTPUT_DIR"

# 2) 必要ファイルの存在確認と不足時の補完
# DWI.mif が無ければ作る
if [[ ! -f DWI.mif ]]; then
  if [[ -f DWI.nii.gz && -f DWI.bvec && -f DWI.bval && -f DWI.json ]]; then
    echo "[Info] DWI.mif を作成します (mrconvert)"
    mrconvert -fslgrad DWI.bvec DWI.bval -json_import DWI.json DWI.nii.gz DWI.mif
  else
    echo "[Error] DWI.mif も DWI.nii.gz/bvec/bval/json も見つかりません。"; exit 1
  fi
fi

# DWI_mask.mif が無ければ白マスクを作る（全ボクセル=1）

echo "[Info] DWI_mask.mif が無いので白マスクを作成します"
mrcalc DWI.mif 0 -eq - | mrcalc - 1 -add DWI_mask.mif


# ROI（seed）存在確認
if [[ ! -f "$ROI_FILE" ]]; then
  echo "[Error] ROI seed ($ROI_FILE) が見つかりません。"; exit 1
fi

# 3) 応答関数 → FOD → トラクト
echo "Step 4: Calculating WM response function..."
dwi2response tournier DWI.mif WM_response_function.tx

echo "Step 5: Generating FOD..."
dwi2fod csd DWI.mif WM_response_function.tx WM_FOD.mif -mask DWI_mask.mif

echo "Step 6: Generating tractography..."
tckgen WM_FOD.mif track.tck -seed_image "$ROI_FILE" -mask DWI_mask.mif -select 20000 -minlength 10

# 4) 付帯出力 (DTI指標の計算)
# dtifit (FSL) の代わりに MRtrix3 の dwi2tensor + tensor2metric を使用
mrconvert DWI_mask.mif DWI_mask.nii.gz
dwi2tensor DWI.mif DWI_tensor.mif -mask DWI_mask.mif
tensor2metric DWI_tensor.mif \
    -fa Files_FA.nii.gz \
    -adc Files_MD.nii.gz \
    -ad  Files_L1.nii.gz \
    -rd  Files_RD.nii.gz

# 5) tractenv3 で FAmap_auto.py を実行（ネイティブ環境のみ venv を切り替え）
if [ -f "$TRACT_VENV" ]; then
    deactivate || true
    source "$TRACT_VENV"
fi

# --- ここで「計算コアの完了」をマーク ---
echo "===FOD_TRACT_CORE_DONE==="


# --- 可視化はバックグラウンド起動（シェルは待たない）---
# スクリプトの位置は冒頭で解決しておく（前回の修正を使用）
"$TRACT_PY" "$SCRIPT_DIR/FAmap_auto.py" "$OUTPUT_DIR" >/dev/null 2>&1 & disown || true

[ -n "${VIRTUAL_ENV:-}" ] && deactivate || true

# # 6) お掃除（必要ファイルだけ残す）
# cd "$OUTPUT_DIR"
# keep_files=("track.tck" "Files_FA.nii.gz" "highlighted_FA.nii.gz" "DWI.nii.gz" "output_mask.nii.gz" "DWI_mask.nii.gz")
# for file in *; do
#   skip=false
#   for keep in "${keep_files[@]}"; do
#     if [[ "$file" == "$keep" ]]; then skip=true; break; fi
#   done
#   if [[ "$skip" == false ]]; then
#     echo "削除: $file"
#     rm -rf "$file"
#   fi
# done

echo "すべての処理が正常に完了しました。"
