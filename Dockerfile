FROM python:3.12-slim

WORKDIR /app

# Ensure pip is up to date
RUN pip install --no-cache-dir --upgrade pip

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create persistent data storage directory and safe non-root user/group
RUN mkdir /data && \
    groupadd -g 1000 appgroup && \
    useradd -r -u 1000 -g appgroup -d /app appuser && \
    chown -R appuser:appgroup /app /data

# Copy app code with appropriate non-root ownership
COPY --chown=appuser:appgroup app /app/app

# Set non-root execution context
USER appuser

EXPOSE 8080

ENV PYTHONUNBUFFERED=1

# Execute app via Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
