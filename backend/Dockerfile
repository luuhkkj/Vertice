FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system vertice \
    && useradd --system --gid vertice --create-home --home-dir /home/vertice vertice

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY --chown=vertice:vertice alembic.ini ./alembic.ini
COPY --chown=vertice:vertice alembic ./alembic
COPY --chown=vertice:vertice app ./app

USER vertice

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import json, urllib.request; data = json.loads(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()); assert data.get('status') == 'healthy'" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
