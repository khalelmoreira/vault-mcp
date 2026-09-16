FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    sudo curl git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash dev \
    && echo "dev ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/dev \
    && chmod 0440 /etc/sudoers.d/dev

WORKDIR /home/dev/workspace/project-vault-mcp

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN chown -R dev:dev /home/dev

USER dev
