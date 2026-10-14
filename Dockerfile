
FROM python:3.11-slim

WORKDIR /app

COPY app/requirements.txt .

# Install CPU-only PyTorch
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu "torch==2.14.0+cpu"

# Install remaining dependencies
RUN pip install --no-cache-dir --default-timeout=120 --retries=5 -r requirements.txt

COPY . /project/
COPY app/ ./app/

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
