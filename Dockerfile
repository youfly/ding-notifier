FROM python:3.12-slim

WORKDIR /app

# 创建非 root 用户
RUN useradd -m -u 1000 appuser

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app.py .
COPY config/ ./config/

# 修改权限
RUN chown -R appuser:appuser /app

USER appuser

# 暴露端口
EXPOSE 5005

# 不需要安装 curl，直接用 python 执行单行脚本
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request as u, os as o; u.urlopen('http://localhost:'+o.environ.get('PORT','5005')+'/health')" || exit 1

CMD ["python", "app.py"]
