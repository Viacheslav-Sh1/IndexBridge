FROM python:3.11-slim

RUN groupadd -r appgroup && useradd -r -g appgroup -u 1000 appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py core.py providers.py security_middleware.py ./

RUN chown -R appuser:appgroup /app && \
    chmod 755 /app && \
    chmod 644 /app/*.py

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=60s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]