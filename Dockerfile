# AquaSentry Production Container Image
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (build-essential for C99 compilation, libgl for headless rendering)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    clang \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy universal platform code
COPY . .

# Compile and verify embedded C99 engine
RUN clang -std=c99 -Wall -Wextra -Werror -c Neural_Network/aquanet_v1.c -o Neural_Network/aquanet_v1.o

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/api/health || exit 1

ENTRYPOINT ["python3", "main.py", "--serve", "--host", "0.0.0.0", "--port", "8000"]
