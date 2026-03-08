FROM python:3.11-slim

# Install ffmpeg
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Create a non-root user and group
RUN groupadd --system app && useradd --system --gid app app

WORKDIR /home/app/web

# Ensure the user owns the files
COPY --chown=app:app requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=app:app . .

# Switch to the new user
USER app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
