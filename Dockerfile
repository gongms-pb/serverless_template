FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_PREFER_BINARY=1 \
    PYTHONUNBUFFERED=1 \
    CMAKE_BUILD_PARALLEL_LEVEL=8 

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        software-properties-common \
        git \
        wget \
        libgl1 \
        git-lfs \
        curl && \
    add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        python3.12-dev && \
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3.12 && \
    ln -sf /usr/bin/python3.12 /usr/bin/python && \
    ln -sf /usr/bin/pip3.12 /usr/bin/pip && \
    git lfs install && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --upgrade pip wheel setuptools && \
    pip install --no-cache-dir huggingface_hub[hf_transfer] && \
    pip install --no-cache-dir torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124 && \
    pip install --no-cache-dir xformers --index-url https://download.pytorch.org/whl/cu124 && \
    pip install --no-cache-dir runpod requests

COPY . /workspace
WORKDIR /workspace

#######################################################################
# EDIT THIS SECTION
ARG HUGGINGFACE_ACCESS_TOKEN=
ARG HUGGINGFACE_REPO=
#######################################################################

# huggingface login and download models
RUN huggingface-cli login --token $HUGGINGFACE_ACCESS_TOKEN && \
    HF_HUB_ENABLE_HF_TRANSFER=1 huggingface-cli download ${HUGGINGFACE_REPO} --local-dir ./ComfyUI/models/

# move some model files to custom nodes
RUN python move_models_to_custom_nodes.py

COPY requirements.txt /tmp/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /tmp/requirements.txt

CMD ["python", "-u", "rp_handler.py"]