FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY app/requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install --index-url https://download.pytorch.org/whl/cpu "torch==2.14.0+cpu" \
    && python -m pip install --default-timeout=120 --retries=5 -r requirements.txt

COPY app/ ./app/

# The application writes audit events to /tmp by default in containers.
ENV QUERYMIND_AUDIT_LOG_PATH=/tmp/querymind-audit.log

RUN useradd --create-home --uid 10001 querymind \
    && chown -R querymind:querymind /app
USER querymind

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
