FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python scripts/rebuild_db.py --skip-downloads

EXPOSE 8081

CMD ["gunicorn", "--bind", "0.0.0.0:8081", "app:app"]
