# 腰椎 FA Tractography Viewer

腰椎の拡散強調MRI（DICOM）から、AIによるROIマスク生成・Tractography・DTI指標（FA/MD/RD）を自動で計算するウェブアプリです。

---

## 動作環境

| 項目 | 要件 |
|---|---|
| OS | Windows / macOS / Linux |
| 必須ソフト | [Docker Desktop](https://www.docker.com/products/docker-desktop/) |
| メモリ | **8GB 以上**（Docker Desktop の割り当て） |
| ストレージ | 約 15GB（Dockerイメージ＋作業領域） |

---

## 事前準備

### 1. Docker Desktop のインストール

[Docker Desktop 公式サイト](https://www.docker.com/products/docker-desktop/) からインストールしてください。

### 2. Docker Desktop のメモリ設定

MRtrix3 のビルドに大量のメモリが必要です。

```
Docker Desktop を開く
→ 右上の歯車アイコン（Settings）
→ Resources
→ Memory を 8GB 以上に設定
→ Apply & Restart
```

### 3. 学習済みモデルファイルの配置

モデルファイル（`20250623_2058_unet_resnet34.pth`、約98MB）を `WebAPI/` フォルダに配置してください。  
※ファイルはサイズが大きいため Git には含まれていません。別途入手してください。

```
WebAPI/
├── 20250623_2058_unet_resnet34.pth  ← ここに置く
├── app.py
├── Dockerfile
└── ...
```

---

## 起動手順

### はじめて起動するとき（初回のみ）

ターミナル（コマンドプロンプト / PowerShell）を開き、`WebAPI` フォルダに移動して以下を実行します。

```bash
cd WebAPI
docker compose up --build
```

> **注意：初回ビルドは 30〜60 分かかります。**  
> MRtrix3 という解析ツールを C++ からコンパイルするためです。  
> 「`Container lumbar-tractography Started`」と表示されたら起動完了です。

### 2回目以降

```bash
cd WebAPI
docker compose up
```

キャッシュが使われるので **数分で起動**します。

### アプリを開く

ブラウザで以下の URL を開いてください。

```
http://localhost:8501
```

### 終了するとき

ターミナルで `Ctrl + C` を押すか、別のターミナルで以下を実行します。

```bash
docker compose down
```

---

## 使い方

### ステップ 1：DICOMフォルダをアップロード

アプリ上の「**DICOMフォルダを選択**」をクリックします。

- フォルダ内の **全 DICOM ファイルを選択**してアップロードしてください
- ファイル拡張子は `.dcm` のほか、拡張子なしのファイルも対応しています
- ファイル数が多い場合（数百枚）でも問題ありません

> **選択方法（Windows）：**  
> ファイル選択画面でフォルダを開き、`Ctrl + A` で全選択 → 「開く」

> **選択方法（macOS）：**  
> ファイル選択画面でフォルダを開き、`Command + A` で全選択 → 「開く」

アップロード後、DICOMのメタ情報（患者情報・撮像条件）が表示されます。

---

### ステップ 2：解析を開始（Stage 1）

「**解析を開始**」ボタンを押します。

内部で以下が自動実行されます：

1. DICOM → NIfTI 変換（`dcm2niix`）
2. UNet ResNet34 による腰椎 ROI マスクの自動生成

処理時間の目安：**1〜3 分**（データ量による）

「解析が完了しました」と表示されたら次のステップへ。

---

### ステップ 3：FOD / Tractography を実行（Stage 2）

「**解析スタート（FOD/Tractography）**」ボタンを押します。

内部で以下が自動実行されます：

1. 白質応答関数の推定（`dwi2response tournier`）
2. Fiber Orientation Distribution（FOD）の計算（`dwi2fod csd`）
3. Tractography の生成（20,000 本のストリームライン）
4. DTI 指標の計算（FA / MD / RD マップ）

処理時間の目安：**5〜15 分**（データ量による）

「FOD/Tractography が完了しました」と表示されたら完了です。

---

### ステップ 4：結果をダウンロード

「**結果を保存（ZIP）**」ボタンを押すと、全出力ファイルを ZIP でダウンロードできます。

#### 出力ファイル一覧

| ファイル名 | 内容 |
|---|---|
| `DWI.nii.gz` | 変換済み NIfTI 画像 |
| `DWI.bvec` / `DWI.bval` | 拡散方向・b値 |
| `output_mask.nii.gz` | AI が予測した腰椎 ROI マスク |
| `WM_FOD.mif` | Fiber Orientation Distribution |
| `track.tck` | Tractography ストリームライン（20,000 本） |
| `Files_FA.nii.gz` | FA（Fractional Anisotropy）マップ |
| `Files_MD.nii.gz` | MD（Mean Diffusivity）マップ |
| `Files_RD.nii.gz` | RD（Radial Diffusivity）マップ |

---

## よくあるトラブル

### アプリが開かない（`http://localhost:8501` に接続できない）

Docker コンテナの起動が完了していない可能性があります。  
ターミナルに `Container lumbar-tractography Started` と表示されるまで待ってください。

### ビルド中にメモリ不足エラーが出る

Docker Desktop の Memory 設定が不足しています。  
Settings → Resources → Memory を **12GB** に増やして再試行してください。

```bash
docker compose build --no-cache
```

### 「解析中にエラーが発生しました」と表示される

「ログを表示」をクリックして内容を確認してください。  
モデルファイル（`.pth`）が `WebAPI/` フォルダに配置されているか確認してください。

### コードを変更した後に反映されない

コードを変更した場合は `--build` オプションが必要です。

```bash
docker compose down
docker compose up --build
```

---

## 処理パイプライン（詳細）

```
DICOM ファイル群
    ↓  dcm2niix
DWI.nii.gz / .bvec / .bval / .json
    ↓  UNet ResNet34 (predict_nif.py)
output_mask.nii.gz  ← 腰椎 ROI マスク
    ↓  mrconvert (MRtrix3)
DWI.mif
    ↓  dwi2response tournier
WM_response_function.tx
    ↓  dwi2fod csd
WM_FOD.mif
    ↓  tckgen (seed: ROI マスク)
track.tck  ← Tractography
    ↓  dwi2tensor + tensor2metric
Files_FA / MD / RD / L1.nii.gz
```

---

## ファイル構成

```
WebAPI/
├── app.py                           # Streamlit メイン UI
├── process1.py                      # Stage 1: DICOM→NIfTI + マスク生成
├── process2.sh                      # Stage 2: FOD + Tractography + DTI
├── predict_nif.py                   # UNet によるセグメンテーション推論
├── dicom_reader.py                  # DICOM メタデータ読み取り
├── makeMask.py                      # マスク手動編集エディタ
├── FAmap_auto.py                    # FA 重み付き 3D 可視化（開発中）
├── 20250623_2058_unet_resnet34.pth  # 学習済みモデル（Git 管理外）
├── Dockerfile                       # Docker イメージ定義
├── docker-compose.yml               # コンテナ起動設定
└── requirements_docker.txt          # Python パッケージ一覧
```

---

## 既知の制限事項

| 制限 | 詳細 |
|---|---|
| 3D 可視化 | Docker ヘッドレス環境では VTK ウィンドウを表示できません。対応予定。 |
| GPU 非対応 | 現在 CPU 推論のみ。GPU を使う場合は Dockerfile 内の `whl/cpu` を `whl/cu121` 等に変更。 |
