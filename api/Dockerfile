FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PYTHONIOENCODING=utf-8 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY api/requirements.txt /app/api/requirements.txt
RUN pip install --no-cache-dir -r /app/api/requirements.txt

COPY api /app/api
COPY shared /app/shared
COPY core /app/core

EXPOSE 8000
CMD ["uvicorn", "api.algofusion_api.main:app", "--host", "0.0.0.0", "--port", "8000"]

