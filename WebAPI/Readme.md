# 腰椎 FA Tractography Viewer

DICOMファイルから腰椎領域のTractographyを自動生成・表示するStreamlitウェブアプリ。

---

## 概要

| 項目 | 内容 |
|---|---|
| 対象部位 | 腰椎（Lumbar spine） |
| 入力 | DICOMファイル群（拡散強調MRI） |
| 出力 | FA map、Tractography (.tck)、DTI指標 |
| インターフェース | Streamlit（ブラウザで操作） |
| 対応OS | Docker経由でWindows / macOS / Linux |

---

## セットアップ（Docker）

### 前提条件

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) がインストール済みであること
- Docker Desktop の **Resources → Memory を 8GB 以上**に設定すること

### 初回ビルド

```bash
cd WebAPI
docker compose build
```

> **注意:** 初回ビルドでは MRtrix3 を C++ からコンパイルするため **30〜60分** かかります。  
> 2回目以降はキャッシュが効くため数分で完了します。

### 起動

```bash
docker compose up
```

ブラウザで `http://localhost:8501` を開く。

### 停止

```bash
docker compose down
```

---

## 使い方

### 解析フロー

```
① DICOMファイルを選択（ブラウザのファイル選択）
        ↓
② 「解析を開始」ボタン
   → DICOM → NIfTI 変換（dcm2niix）
   → UNet ResNet34 による腰椎 ROI マスク自動生成
        ↓
③ マスク確認・編集（必要に応じて）
        ↓
④ 「解析スタート（FOD/Tractography）」ボタン
   → Fiber Orientation Distribution (FOD) 計算
   → Tractography 生成（20,000本のストリームライン）
   → FA / MD / RD マップ計算
        ↓
⑤ 結果を ZIP でダウンロード
```

### DICOMの選択方法

アプリ上のファイルアップローダーから **フォルダ内のDICOMファイルを複数選択** してアップロードします。  
ファイル拡張子は `.dcm` のほか、拡張子なしのファイルも対応しています。

### 出力ファイル

| ファイル | 内容 |
|---|---|
| `DWI.nii.gz` | 変換後のNIfTI画像 |
| `DWI.bvec / .bval` | 拡散方向・b値 |
| `output_mask.nii.gz` | AIが予測したROIマスク |
| `WM_FOD.mif` | Fiber Orientation Distribution |
| `track.tck` | Tractographyストリームライン |
| `Files_FA.nii.gz` | FA（Fractional Anisotropy）マップ |
| `Files_MD.nii.gz` | MD（Mean Diffusivity）マップ |

---

## データの配置（任意）

`docker compose up` 前にDICOMデータをボリュームとして渡すこともできます：

```
WebAPI/
└── data/
    └── patient_01/
        ├── IM-0001.dcm
        ├── IM-0002.dcm
        └── ...
```

コンテナ内では `/app/data/` としてマウントされます。

---

## 処理パイプライン詳細

### Stage 1（`process1.py`）

1. `dcm2niix` でDICOMをNIfTI形式に変換
2. UNet ResNet34（`20250623_2058_unet_resnet34.pth`）で腰椎ROI領域をセグメンテーション

### Stage 2（`process2.sh`）

1. `mrconvert` でNIfTI → MIF変換（MRtrix3形式）
2. `dwi2response tournier` で白質応答関数を推定
3. `dwi2fod csd` でFODを計算
4. `tckgen` でTractographyを生成（seed: ROIマスク、20,000本）
5. `dwi2tensor` + `tensor2metric` でDTI指標（FA/MD/RD）を算出

---

## ファイル構成

```
WebAPI/
├── app.py                  # StreamlitメインUI
├── process1.py             # Stage1: DICOM→NIfTI + マスク予測
├── process2.sh             # Stage2: FOD + Tractography生成
├── predict_nif.py          # UNetによるROIセグメンテーション
├── makeMask.py             # マスク手動編集エディタ
├── FAmap_auto.py           # FA重み付き3D可視化
├── dicom_reader.py         # DICOMメタデータ読み取り
├── file_dialog.py          # フォルダ選択ユーティリティ（ネイティブ環境用）
├── utils/
│   └── path_utils.py       # パス検証ユーティリティ
├── 20250623_2058_unet_resnet34.pth  # 学習済みモデル（98MB）
├── Dockerfile              # Dockerイメージ定義
├── docker-compose.yml      # コンテナ起動設定
├── requirements_docker.txt # Docker用Pythonパッケージ
├── requirements_App.txt    # ネイティブ環境（.Appenv）用
├── requirements_smp.txt    # セグメンテーション環境（.smpenv）用
├── requirements_mrtrix.txt # MRtrix3環境（.mrtrixenv）用
└── requirements_tract.txt  # Tractography可視化環境（.tractenv3）用
```

---

## ネイティブ環境での実行（macOS）

Docker不使用で直接実行する場合（macOS推奨）：

```bash
# 仮想環境を有効化
source .Appenv/bin/activate

# Streamlitを起動
streamlit run app.py
```

> MRtrix3はmacOSで動作しますが、Windowsでは非対応のため Docker を使用してください。

---

## 既知の制限事項

| 制限 | 詳細 |
|---|---|
| 3D可視化（FAmap_auto.py） | Docker（ヘッドレス）環境ではVTKウィンドウを表示できない。別途対応予定。 |
| GPU非対応 | 現在CPU推論のみ。GPUが必要な場合は Dockerfile の PyTorch インストール行の `whl/cpu` を `whl/cu121` 等に変更。 |

---

## 開発者向け情報

### Docker イメージの構成

```
Stage 1 (mrtrix-builder)
  ├─ Debian Trixie ベース
  ├─ MRtrix3 3.0.4 をソースからビルド（-nogui）
  └─ ビルド成果物: /opt/mrtrix3/bin + lib

Stage 2 (最終イメージ)
  ├─ Stage1 から MRtrix3 バイナリのみコピー
  ├─ conda: Python 3.12, dcm2niix, tk
  ├─ pip: PyTorch CPU, Streamlit, DIPY, segmentation-models-pytorch ...
  └─ アプリ本体
```

### ビルド時の注意

- Docker Desktop のメモリを **8GB 以上** に設定する
- MRtrix3 のコンパイルに **30〜60分** かかる（初回のみ）
- Apple Silicon (M1/M2/M3) では `linux/amd64` をQEMUエミュレーションで実行するため、ビルドが遅くなる

### イメージの再ビルドが必要なケース

- `Dockerfile` や `requirements_docker.txt` を変更したとき
- `--no-cache` で完全な再ビルド: `docker compose build --no-cache`
