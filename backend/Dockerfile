FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (required for ping3 / raw sockets)
RUN apt-get update && apt-get install -y iputils-ping libcap2-bin && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Allow python binary to bind raw sockets without running as full root
RUN setcap cap_net_raw+ep /usr/local/bin/python3.11

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
