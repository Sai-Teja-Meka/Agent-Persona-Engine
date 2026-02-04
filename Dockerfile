FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port (Railway uses $PORT env var)
EXPOSE 8000

# Start FastAPI
CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

**Create `.dockerignore`:**
```
frontend/
node_modules/
__pycache__/
*.pyc
.env
.git/
venv/