# Force rebuild - Pharma FAQ RAG System
# Standard python image
FROM python:3.11-slim

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies (as root into system path)
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root user (UID 1000 is default for HF Spaces)
RUN useradd -m -u 1000 user

WORKDIR /app

# Copy application code and set ownership
COPY --chown=user . .

# Generate sample FAQ PDFs and ingest data (as user)
USER user
RUN python3 generate_faqs.py && python3 ingest.py

# Final check: ensure data files are writable by the runtime user
# (This is redundant since we run as 'user' but ensures no root-owned files remain)
RUN chmod -R 777 /app/vector_db /app/faq_metadata.db

# Expose Streamlit port
EXPOSE 7860

# Run Streamlit on port 7860
CMD ["streamlit", "run", "app.py", "--server.port=7860", "--server.address=0.0.0.0", "--server.headless=true", "--browser.gatherUsageStats=false"]
