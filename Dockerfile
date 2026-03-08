FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# System deps
RUN apt-get update && apt-get install -y \
    python3.11 python3.11-dev python3-pip \
    curl nodejs npm \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1

WORKDIR /app

# Backend
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Frontend
COPY frontend/package.json /app/frontend/package.json
WORKDIR /app/frontend
RUN npm install
COPY frontend/ /app/frontend/
RUN npm run build

# Copy built frontend into backend static dir
RUN mkdir -p /app/backend/frontend && cp -r /app/frontend/dist /app/backend/frontend/dist

# Copy backend source
WORKDIR /app
COPY backend/ /app/backend/

WORKDIR /app/backend

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
