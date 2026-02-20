# ─────────────────────────────────────────────────────────────────────────────
# UNIVERSAL POLYGLOT RUNTIME (The "Kitchen Sink")
# ─────────────────────────────────────────────────────────────────────────────
# Supports:
# - Python 3.11 (pytest)
# - Node.js 20  (npm / yarn / jest)
# - Java 17     (maven / gradle)
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# 1. Install System dependencies + OpenJDK 17 + Maven + Gradle
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jdk-headless \
    maven \
    gradle \
    git \
    curl \
    build-essential \
    ca-certificates \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# 2. Install Node.js 20.x (official release)
RUN mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && apt-get install -y nodejs && \
    npm install -g yarn && \
    rm -rf /var/lib/apt/lists/*

# 3. Verify versions (fail build if missing)
RUN python3 --version && \
    node --version && \
    npm --version && \
    java -version && \
    mvn -version && \
    gradle -version

# 4. Pre-install Python testing essentials
RUN pip install --no-cache-dir \
    pytest \
    pytest-json-report \
    flake8 \
    pylint \
    black \
    mypy

# 5. Set Environment
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

WORKDIR /workspace

# Default command (overridden by agent)
CMD ["/bin/bash"]
