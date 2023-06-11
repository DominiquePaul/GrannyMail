FROM python:3.11-slim-bullseye
RUN apt-get update && apt-get upgrade -y && pip install --upgrade pip  && apt-get install -y git

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

# Install from the requirements.txt 
# We run this before copying everything else as changes are cached. We don't
# want to reinstall dependencies if a random other file changes.
COPY requirements.txt .
RUN pip install --upgrade pip && python -m pip install -r requirements.txt

# Make the directory the working directory for subsequent commands
WORKDIR /app
# Place the application components in our app dir (a dir below the root dir)
COPY . /app

# Creates a non-root user with an explicit UID and adds permission to access the /app folder
# For more info, please refer to https://aka.ms/vscode-docker-python-configure-containers
# chown hands everything over to the 'app' user
RUN adduser -u 5678 --disabled-password --gecos "" appuser && chown -R appuser /app
# Subsequent commands, either in this Dockerfile or in a
# docker-compose.yml, will run as user 'app'
USER appuser