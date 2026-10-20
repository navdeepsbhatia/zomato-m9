FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY src ./src
COPY data/processed/restaurants.csv ./data/processed/restaurants.csv

ENV PYTHONUNBUFFERED=1
CMD python -m uvicorn app.api:app --host 0.0.0.0 --port ${PORT:-8000}
