# ============================================================
# Stage 1: MRtrix3 をソースからビルド
# conda-forge に linux-64 パッケージが存在しないためソースビルド必須
# ============================================================
FROM --platform=linux/amd64 continuumio/miniconda3:latest AS mrtrix-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        git python3 g++ make \
        libeigen3-dev libfftw3-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# MRtrix3 3.0.4 をクローン＆ビルド (-nogui でQt不要)
# ※ build 1 でシングルジョブ指定: 並列ビルドはメモリを大量消費するため
#    Docker Desktop のメモリは最低 8GB 必要 (Settings > Resources > Memory)
RUN git clone --depth 1 --branch 3.0.4 \
        https://github.com/MRtrix3/mrtrix3.git /opt/mrtrix3 \
    && cd /opt/mrtrix3 \
    && python3 configure -nogui \
    && NUMBER_OF_PROCESSORS=2 python3 build

# ============================================================
# Stage 2: メインイメージ
# ============================================================
FROM --platform=linux/amd64 continuumio/miniconda3:latest

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VTK_DEFAULT_RENDER_WINDOW_OFFSCREEN=1

# システムパッケージ
# libfftw3-dev: Debian Trixie で libfftw3-3 が libfftw3-3t64 にリネームされたため
#               -dev パッケージ経由で正しいランタイムが引き込まれる（Bookworm/Trixie 両対応）
# libglib2.0-0 / libsm6 / libxext6 / libxrender1 はヘッドレス構成では不要
RUN apt-get update && apt-get upgrade -y --no-install-recommends && \
    apt-get install -y --no-install-recommends \
        libfftw3-dev \
        zlib1g \
        libgl1 \
        libgomp1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# MRtrix3 バイナリ + Python スクリプト用 lib をコピー
COPY --from=mrtrix-builder /opt/mrtrix3/bin /opt/mrtrix3/bin
COPY --from=mrtrix-builder /opt/mrtrix3/lib /opt/mrtrix3/lib
ENV PATH="/opt/mrtrix3/bin:${PATH}"

# Python 3.11 + dcm2niix + Tk
# MRtrix3 の Python スクリプト (dwi2response等) が import imp を使用しており
# Python 3.12 では imp が廃止されたため 3.11 を使用する
RUN conda install -y -c conda-forge python=3.11 dcm2niix tk && \
    conda clean -afy

WORKDIR /app

# PyTorch CPU 版（GPU が必要な場合は whl URL を cu121 等に変更）
RUN pip install --no-cache-dir \
        torch torchvision torchaudio \
        --index-url https://download.pytorch.org/whl/cpu

# アプリ依存パッケージ
COPY requirements_docker.txt .
RUN pip install --no-cache-dir -r requirements_docker.txt

# アプリ本体とモデルファイルをコピー
COPY . .

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["streamlit", "run", "app.py", \
    "--server.address=0.0.0.0", \
    "--server.port=8501", \
    "--server.headless=true", \
    "--server.maxUploadSize=2000"]
