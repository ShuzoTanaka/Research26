import os

def is_dicom_folder(path):
    return any(f.endswith(".dcm") for f in os.listdir(path))
