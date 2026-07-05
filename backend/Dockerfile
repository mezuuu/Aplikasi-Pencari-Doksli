# Gunakan image Python ringan
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=7860

# Install dependencies sistem untuk OpenCV
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
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

# Expose port (Hugging Face Spaces default 7860, Render default 10000)
EXPOSE 7860

# Jalankan server menggunakan Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:7860", "--workers", "2", "--timeout", "120", "config.wsgi:application"]
