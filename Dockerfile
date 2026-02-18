FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV COMFYUI_PORT=8188
ENV COMFYUI_PATH=/opt/comfyui

# System dependencies
RUN apt-get update && apt-get install -y \
    python3.10 python3-pip python3.10-venv \
    git wget curl libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3.10 /usr/bin/python && \
    ln -sf /usr/bin/pip3 /usr/bin/pip

# Install ComfyUI
RUN git clone https://github.com/comfyanonymous/ComfyUI.git $COMFYUI_PATH && \
    cd $COMFYUI_PATH && \
    pip install --no-cache-dir -r requirements.txt

# Install custom nodes
WORKDIR $COMFYUI_PATH/custom_nodes

RUN git clone https://github.com/Gourieff/comfyui-reactor-node.git && \
    cd comfyui-reactor-node && pip install --no-cache-dir -r requirements.txt

RUN git clone https://github.com/cubiq/ComfyUI_IPAdapter_plus.git && \
    cd ComfyUI_IPAdapter_plus && \
    pip install --no-cache-dir -r requirements.txt 2>/dev/null || true

# Download models
WORKDIR $COMFYUI_PATH

# FLUX.1-dev
RUN mkdir -p models/unet && \
    wget -q --show-progress -O models/unet/flux1-dev.safetensors \
    "https://huggingface.co/black-forest-labs/FLUX.1-dev/resolve/main/flux1-dev.safetensors" || \
    echo "FLUX model must be provided at runtime or via volume mount"

# CLIP models for FLUX
RUN mkdir -p models/clip && \
    wget -q -O models/clip/clip_l.safetensors \
    "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors" || true && \
    wget -q -O models/clip/t5xxl_fp16.safetensors \
    "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp16.safetensors" || true

# VAE for FLUX
RUN mkdir -p models/vae && \
    wget -q -O models/vae/ae.safetensors \
    "https://huggingface.co/black-forest-labs/FLUX.1-dev/resolve/main/ae.safetensors" || true

# ReActor face swap model
RUN mkdir -p models/insightface/models/buffalo_l && \
    wget -q -O models/insightface/inswapper_128.onnx \
    "https://github.com/facefusion/facefusion-assets/releases/download/models/inswapper_128.onnx" || true

# Install handler dependencies
WORKDIR /opt/handler
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy handler source
COPY src/ ./src/
COPY workflows/ ./workflows/

ENV PYTHONPATH=/opt/handler

CMD ["python", "-u", "src/handler.py"]
