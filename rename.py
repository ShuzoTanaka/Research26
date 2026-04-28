import os
import pydicom
import csv
from pathlib import Path

def organize_by_dicom_id(src_root, dst_root):
    src_path = Path(src_root)
    dst_path = Path(dst_root)
    
    mapping_data = []
    processed_patients = set()

    # DICOMファイルが含まれるフォルダを探す
    dicom_dirs = set()
    for dcm in src_path.rglob("*.dcm"):
        dicom_dirs.add(dcm.parent)

    print(f"解析開始: {len(dicom_dirs)} 個のフォルダを処理します。")

    for folder in dicom_dirs:
        # フォルダ内の最初のファイルから情報を取得
        sample_file = next(folder.glob("*.dcm"))
        try:
            ds_info = pydicom.dcmread(sample_file, stop_before_pixels=True)
            
            # DICOMタグから情報を取得
            # 取得できない場合のデフォルト値を設定
            patient_id = getattr(ds_info, 'PatientID', 'UNKNOWN_ID')
            original_name = str(getattr(ds_info, 'PatientName', 'UNKNOWN_NAME'))

            # 新しい保存先: dst_root / 患者ID / 元のフォルダ名
            # 例: /Organized/1234567/Tract~
            new_parent_dir = dst_path / str(patient_id) / folder.name
            new_parent_dir.mkdir(parents=True, exist_ok=True)

            # フォルダ内の全DICOMを処理
            for dcm_file in folder.glob("*.dcm"):
                ds = pydicom.dcmread(dcm_file)
                
                # 患者名は削除またはIDに置き換えて匿名化を徹底
                ds.PatientName = str(patient_id)
                
                # ファイルを保存
                ds.save_as(new_parent_dir / dcm_file.name)

            # 対応表用のデータを記録（一度だけ）
            if patient_id not in processed_patients:
                mapping_data.append([original_name, patient_id])
                processed_patients.add(patient_id)
            
            print(f"完了: {original_name} -> ID:{patient_id} / フォルダ:{folder.name}")

        except Exception as e:
            print(f"エラー発生 (フォルダ: {folder}): {e}")

    # 対応表の保存
    with open(dst_path / "id_mapping_list.csv", "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Original Name", "Chart Number (PatientID)"])
        writer.writerows(mapping_data)

    print("\nすべての処理が完了しました。")

# --- 設定 ---
# 元データが入っているディレクトリ
raw_data_dir = "/Users/tanakashuuzou/Research/データ"
# 整理後の出力先
new_data_dir = "/Users/tanakashuuzou/Research/Organized_By_ID"

organize_by_dicom_id(raw_data_dir, new_data_dir)