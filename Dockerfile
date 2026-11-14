FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Build the DB at image-build time, downloading sources fresh (default).
RUN python scripts/rebuild_db.py

EXPOSE 8081

# --no-control-socket: gunicorn 25.1.0 starts the control socket's asyncio
# thread in the arbiter before forking workers, and the forked worker then
# deadlocks on the inherited logging lock (it never gets past "Booting worker").
# The listen socket still accepts, so requests hang instead of failing -> 524.
CMD ["gunicorn", "--no-control-socket", "--bind", "0.0.0.0:8081", "app:app"]
