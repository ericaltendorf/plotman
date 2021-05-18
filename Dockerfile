FROM ghcr.io/chia-network/chia:latest
COPY . /plotman
ENV PATH="/chia-blockchain/venv/bin:$PATH"
RUN apt update && \
    apt install pip -y && \
    rm -rf /var/lib/apt/lists && \
    pip install -e /plotman
