FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/app/data

WORKDIR /app
RUN addgroup --system app && adduser --system --ingroup app app \
    && mkdir -p /app/data && chown -R app:app /app

COPY requirements.txt requirements.local.txt ./
RUN pip install --no-cache-dir -r requirements.local.txt
COPY app ./app
COPY scripts ./scripts
RUN chown -R app:app /app

USER app
EXPOSE 8000
HEALTHCHECK --interval=20s --timeout=5s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
