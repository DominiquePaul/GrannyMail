FROM python:3.11-slim
ENV PYTHONUNBUFFERED True
WORKDIR /
COPY requirements.txt .
# required for pyproject.toml based projects
RUN apt-get update && \
    apt-get install -y gcc libc6-dev
RUN pip install --no-cache-dir --upgrade pip -r requirements.txt
COPY . ./

CMD exec gunicorn grannymail.telegrambot:app -k uvicorn.workers.UvicornWorker -b :8000 --workers 1 --threads 8 --timeout 0
