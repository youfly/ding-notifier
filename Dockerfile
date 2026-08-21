FROM python:3.12-slim

WORKDIR /app

# 安装 curl 用于健康检查，并清理缓存减小体积
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY config/ ./config/

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

# 动态端口健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:${PORT:-5000}/health || exit 1

CMD ["python", "app.py"]
