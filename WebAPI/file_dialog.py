import tkinter as tk
from tkinter import filedialog
import multiprocessing

def choose(folder_path_dict):
    root = tk.Tk()
    root.withdraw()
    path = filedialog.askdirectory()
    folder_path_dict["value"] = path
    root.destroy()

def select_folder_safe():
    manager = multiprocessing.Manager()
    folder_path = manager.dict()

    ctx = multiprocessing.get_context("spawn")
    p = ctx.Process(target=choose, args=(folder_path,))
    p.start()
    p.join()

    return folder_path.get("value", "")
