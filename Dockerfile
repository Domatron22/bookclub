# Initial css build stage
FROM node:20-slim AS css-builder

WORKDIR /app

# Copy Tailwind config and package files
COPY package.json tailwind.config.js ./
COPY app/static/css/input.css ./app/static/css/

# Install Node dependencies and build CSS
RUN npm install
RUN mkdir -p app/templates && \
    mkdir -p app/static/js
COPY app/templates ./app/templates
COPY app/static/js ./app/static/js
RUN npm run build:css

# Python application stage
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy Python requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ./app ./app

# Copy built CSS from css-builder stage
COPY --from=css-builder /app/app/static/css/tailwind.css ./app/static/css/

# Create data directory
RUN mkdir -p /app/data

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]