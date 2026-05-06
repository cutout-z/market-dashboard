FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code is bind-mounted at runtime (see docker-compose.yml).
# The COPY here is only so the image can run standalone without a volume mount.
COPY . .

EXPOSE 8060

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8060"]
