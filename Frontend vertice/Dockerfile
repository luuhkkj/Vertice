FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

RUN groupadd --system vertice \
    && useradd --system --gid vertice --create-home --home-dir /home/vertice vertice

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY --chown=vertice:vertice app.py config.py ./
COPY --chown=vertice:vertice assets ./assets
COPY --chown=vertice:vertice components ./components
COPY --chown=vertice:vertice data ./data
COPY --chown=vertice:vertice pages ./pages
COPY --chown=vertice:vertice styles ./styles
COPY --chown=vertice:vertice utils ./utils

USER vertice

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; resp = urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=3); assert resp.status == 200" || exit 1

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
