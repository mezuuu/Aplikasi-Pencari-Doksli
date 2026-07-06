# Gunakan image Python ringan
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=7860

# Install dependencies sistem untuk OpenCV
RUN apt-get update && apt-get install -y \
    ca-certificates \
    wget \
    libgl1 \
    libglib2.0-0 \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-ind \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Add a lightweight OpenCV DNN face detector for production privacy fallback.
RUN mkdir -p /app/models && \
    wget -q -O /app/models/deploy.prototxt \
        https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt && \
    wget -q -O /app/models/res10_300x300_ssd_iter_140000.caffemodel \
        https://github.com/opencv/opencv_3rdparty/raw/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel && \
    wget -q -O /app/models/haarcascade_frontalface_default.xml \
        https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml && \
    wget -q -O /app/models/haarcascade_frontalface_alt2.xml \
        https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_alt2.xml && \
    wget -q -O /app/models/haarcascade_profileface.xml \
        https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_profileface.xml

# Copy requirements dan install
COPY requirements.txt /app/
# Install versi CPU dari PyTorch agar ukurannya lebih kecil (wajib untuk server gratis)
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt
RUN python -c "import cv2; assert hasattr(cv2, 'CascadeClassifier'), 'OpenCV CascadeClassifier missing'; assert hasattr(cv2, 'dnn'), 'OpenCV dnn module missing'; assert hasattr(cv2.dnn, 'readNetFromCaffe'), 'OpenCV Caffe DNN loader missing'"

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
