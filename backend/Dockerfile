# Gunakan image Python ringan
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=7860

# Install dependencies sistem untuk OpenCV
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements dan install
COPY requirements.txt /app/
# Install versi CPU dari PyTorch agar ukurannya lebih kecil (wajib untuk server gratis)
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# Copy seluruh kode backend
COPY . /app/

# Buat folder media dan database jika menggunakan SQLite
RUN mkdir -p /app/media /app/db
RUN chmod -R 777 /app/media /app/db

# Copy entrypoint script dan beri izin eksekusi
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Expose port (Hugging Face Spaces default 7860)
EXPOSE 7860

# Jalankan entrypoint: migrate → collectstatic → gunicorn
CMD ["/bin/bash", "/app/entrypoint.sh"]
