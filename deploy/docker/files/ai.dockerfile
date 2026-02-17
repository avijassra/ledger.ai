FROM python:3.11-slim
WORKDIR /app

# Copy requirements from the ai/api folder
COPY src/server/services/ai/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the AI source code
COPY src/server/services/ai/api/ .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]