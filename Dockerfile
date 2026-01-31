FROM mcr.microsoft.com/playwright/python:v1.57.0-noble

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    sqlite3 \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY archiveit ./archiveit

ENV ARCHIVEIT_DATA_DIR=/data
ENV ARCHIVEIT_DB_PATH=/data/archiveit.db
ENV ARCHIVEIT_REDIS_URL=redis://redis:6379/0

EXPOSE 8000

CMD ["uvicorn","archiveit.main:app","--host","0.0.0.0","--port","8000"]

ENTRYPOINT []
