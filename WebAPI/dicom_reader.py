import os
import pydicom

class DICOMReader:
    def __init__(self, folder_path):
        self.folder_path = folder_path
        self.files = self._load_files()

    def _load_files(self):
        return [f for f in os.listdir(self.folder_path) if f.endswith(".dcm")]

    def get_basic_info(self):
        if not self.files:
            return {"error": "DICOMファイルが見つかりません"}
        sample = pydicom.dcmread(os.path.join(self.folder_path, self.files[0]))
        return {
            "PatientName": str(sample.get("PatientName", "不明")),
            "Modality": str(sample.get("Modality", "不明")),
            "NumberOfFiles": len(self.files)
        }
