#!/usr/bin/env python3
# process1.py
# DICOM -> NIfTI 変換（dcm2niix）→ .smpenv の python で predict_nif.py を実行して mask 作成

import os
import sys
import subprocess
from pathlib import Path
import argparse

def run_analysis(dicom_dir: str, output_dir: str,
                 smp_python: str | None = None,
                 predict_script: str | None = None) -> dict:
    dicom_dir = Path(dicom_dir).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not dicom_dir.exists():
        raise FileNotFoundError(f"DICOMフォルダが見つかりません: {dicom_dir}")

    # --- Step 1: DICOM → NIfTI (dcm2niix) ---
    print("Step1: DICOMファイルをNIFTIに変換中...")
    cmd_dcm2niix = [
        "dcm2niix", "-o", str(output_dir), "-f", "DWI", "-b", "y", "-z", "y", str(dicom_dir)
    ]
    res = subprocess.run(cmd_dcm2niix, capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stdout)
        print(res.stderr, file=sys.stderr)
        raise RuntimeError("dcm2niix が失敗しました")

    nifti_file = output_dir / "DWI.nii.gz"
    bvec_file  = output_dir / "DWI.bvec"
    bval_file  = output_dir / "DWI.bval"
    json_file  = output_dir / "DWI.json"

    for p in (nifti_file, bvec_file, bval_file, json_file):
        if not p.exists():
            raise FileNotFoundError(f"期待した出力が見つかりません: {p}")

    # --- Step 2: 深層学習で mask 予測 (.smpenv の python で実行) ---
    print("Step2: 深層学習を用いてNIfTIからmask領域を推定中...")
    if smp_python is None:
        # Docker/単一環境: 現在の Python インタープリタをそのまま使用
        # ネイティブ環境で別 venv を使う場合は --smp-python で指定
        smp_python = sys.executable
    if predict_script is None:
        predict_script = "predict_nif.py"  # カレント or PATH の想定

    smp_python_path = Path(smp_python)
    if not smp_python_path.exists():
        raise FileNotFoundError(f".smpenv の python が見つかりません: {smp_python_path}")

    predict_script_path = Path(predict_script)
    if not predict_script_path.exists():
        # 明示パスで無ければ、カレント/実行場所の相対に無いかもしれないのでメッセージ
        raise FileNotFoundError(f"predict_nif.py が見つかりません: {predict_script_path}")

    cmd_predict = [str(smp_python_path), str(predict_script_path), str(output_dir)]
    res2 = subprocess.run(cmd_predict, capture_output=True, text=True)
    if res2.returncode != 0:
        print(res2.stdout)
        print(res2.stderr, file=sys.stderr)
        raise RuntimeError("predict_nif.py の実行に失敗しました")

    roi_file = output_dir / "output_mask.nii.gz"
    if not roi_file.exists():
        raise FileNotFoundError(f"mask ファイルが生成されていません: {roi_file}")

    print("=== Done ===")
    return {
        "nifti": str(nifti_file),
        "bvec":  str(bvec_file),
        "bval":  str(bval_file),
        "json":  str(json_file),
        "mask":  str(roi_file),
        "output_dir": str(output_dir),
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dicom_dir", help="DICOM フォルダのパス")
    parser.add_argument("output_dir", help="出力フォルダのパス")
    parser.add_argument("--smp-python", dest="smp_python",
                        help="smpenv の python へのパス（未指定なら既定パスを使用）")
    parser.add_argument("--predict-script", dest="predict_script",
                        help="predict_nif.py のパス（未指定ならカレントの predict_nif.py を使用）")
    args = parser.parse_args()

    info = run_analysis(args.dicom_dir, args.output_dir,
                        smp_python=args.smp_python,
                        predict_script=args.predict_script)
    # 必要ならここで JSON で返すなどしてもOK
    print(info)
