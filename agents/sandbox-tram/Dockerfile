# Sandbox disbursement agent — AgentBase runtime (port 8080, GET /health)
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Bake the synthetic dataset into the image so the agent has data on startup.
RUN python generate_data.py

EXPOSE 8080
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
