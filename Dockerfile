#FROM python:3.10.6
FROM pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime

WORKDIR /subsai

COPY requirements.txt .

ENV DEBIAN_FRONTEND noninteractive
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y \
        git \
        gcc \
        mono-mcs \
        curl \
        htop \
        procps \
        && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml .
COPY ./src ./src
COPY ./assets ./assets

RUN pip install .

# Create data directory for SQLite database persistence
RUN mkdir -p /subsai/data && chmod 755 /subsai/data

# Copy and setup health check script
COPY scripts/healthcheck.sh /usr/local/bin/healthcheck.sh
RUN chmod +x /usr/local/bin/healthcheck.sh

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD /usr/local/bin/healthcheck.sh

EXPOSE 8501

ENTRYPOINT ["python", "src/subsai/webui.py", "--server.fileWatcherType", "none", "--browser.gatherUsageStats", "false"]

