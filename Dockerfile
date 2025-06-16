FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application
COPY . .

# Run the application
CMD ["uvicorn", "relay_app:app", "--host", "0.0.0.0", "--port", "8000"] 