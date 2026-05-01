# CLAUDE.md

Claude Code がこのリポジトリで作業するときに参照するファイル。

## リポジトリ概要

**Research26** — 腰椎MRI解析研究プロジェクト（田中 ShuzoTanaka）
- GitHub: `git@github.com:ShuzoTanaka/Research26.git`
- 主要コンポーネント: DICOMファイル整理スクリプト + Tractography WebApp

---

## ディレクトリ構成

```
Research/
├── rename.py          # DICOMファイル整理・匿名化スクリプト
├── WebAPI/            # 腰椎FA Tractography Viewer（Streamlit + Docker）
└── .gitignore
```

---

## WebAPI — 腰椎FA Tractography Viewer

### 概要

| 項目 | 内容 |
|---|---|
| フレームワーク | Streamlit |
| 実行環境 | Docker（linux/amd64）推奨 |
| 対象 | 腰椎拡散強調MRI（DICOM入力） |
| 出力 | FA map、Tractography (.tck)、DTI指標 |

### 起動方法

```bash
cd WebAPI
docker compose up --build   # 初回・コード変更後
docker compose up           # 2回目以降（変更なし）
docker compose down         # 停止
```

ブラウザで `http://localhost:8501` を開く。

> 初回ビルドはMRtrix3のC++コンパイルで30〜60分かかる。  
> Docker Desktopのメモリは8GB以上必要（Settings > Resources > Memory）。

### 処理フロー

```
① DICOMフォルダ選択（ブラウザのファイルアップローダー）
② process1.py: dcm2niix で NIfTI変換 → UNet ResNet34 で腰椎ROIセグメンテーション
③ process2.sh: FOD計算（dwi2fod）→ Tractography生成（tckgen）→ DTI指標計算
④ 結果をZIPダウンロード
```

### 主要ファイル

| ファイル | 役割 |
|---|---|
| `app.py` | StreamlitメインUI。webkitdirectoryでフォルダ選択。 |
| `process1.py` | DICOM→NIfTI変換（dcm2niix）＋AIマスク生成呼び出し |
| `process2.sh` | MRtrix3パイプライン（FOD/Tractography/DTI） |
| `predict_nif.py` | UNet ResNet34によるROIセグメンテーション推論 |
| `Dockerfile` | マルチステージビルド（Stage1: MRtrix3コンパイル / Stage2: 本番） |
| `docker-compose.yml` | コンテナ起動設定 |
| `requirements_docker.txt` | Docker用Pythonパッケージ |
| `20250623_2058_unet_resnet34.pth` | 学習済みモデル（98MB・gitignore対象） |

### 重要な技術的注意点

- **Python 3.11 必須**: MRtrix3 3.0.4 は `import imp` を使用。Python 3.12 では `imp` 廃止のため動かない。
- **`torch.load` は `weights_only=False`**: PyTorch 2.6以降のデフォルト変更対応済み。
- **`opencv-python-headless`**: ヘッドレス環境では `opencv-python` ではなくこちらを使う。
- **`libfftw3-dev`**: Debian Trixieで `libfftw3-3` が `libfftw3-3t64` にリネームされたため `-dev` 経由で導入。
- **`dtifit`（FSL）は未インストール**: `dwi2tensor` + `tensor2metric`（MRtrix3）で代替済み。
- **モデルパスはスクリプト相対パス**: `Path(__file__).parent / "モデルファイル名"` で解決。

### 既知の制限

- **3D可視化（FAmap_auto.py）**: Dockerヘッドレス環境ではVTKウィンドウ表示不可。対応予定。
- **GPU非対応**: 現在CPU推論のみ。GPU対応は Dockerfile の whl URL を `cu121` 等に変更。

---

## rename.py — DICOMファイル整理

```bash
pip install pydicom
python rename.py   # スクリプト内のパスを編集してから実行
```

- `raw_data_dir`: 元DICOMフォルダ
- `new_data_dir`: 整理後の出力先
- 出力: `<PatientID>/<元フォルダ名>/IM-*.dcm` + `id_mapping_list.csv`（患者名→ID対応表）

---

## gitignore 除外対象

コミットしてはいけないもの：
- `*.pth`, `*.h5`, `*.onnx`（モデルファイル）
- `*.nii`, `*.nii.gz`, `*.dcm`（医療データ）
- `*.mif`, `*.tck`, `*.bvec`, `*.bval`（MRtrix3出力）
- `WebAPI/data/`, `WebAPI/output/`（解析データ）
- 仮想環境ディレクトリ（`.Appenv`, `.mrtrixenv` 等）
