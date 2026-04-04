# Force rebuild - Pharma FAQ RAG System
FROM python:3.11-slim

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root user (UID 1000 for HF Spaces)
RUN useradd -m -u 1000 user

WORKDIR /app

# Copy application code
COPY . .

# Run ingestion as root to ensure directories can be created
# Then change ownership to 'user'
RUN python3 ingest.py && \
    chown -R user:user /app && \
    chmod -R 777 /app/vector_db /app/faq_metadata.db

# Switch to non-root user for runtime
USER user

# Expose Streamlit port
EXPOSE 7860

# Run Streamlit
CMD ["streamlit", "run", "app.py", "--server.port=7860", "--server.address=0.0.0.0", "--server.headless=true", "--browser.gatherUsageStats=false"]
