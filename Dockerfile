# Farm Camera Animal Detection - Docker Image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY *.py .

# Create directory for captured images
RUN mkdir -p /app/captured_images

# Run the application
CMD ["python", "main.py"]
