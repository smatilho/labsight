FROM python:3.12-slim

WORKDIR /app

# Create non-root user
RUN useradd -m -u 1000 labsight

# Install dependencies first for layer caching
COPY --chown=labsight:labsight requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=labsight:labsight app/ app/

USER labsight

EXPOSE 8080

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
