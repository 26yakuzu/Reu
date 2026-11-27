# Optional container. Data are NOT baked in: mount ./data at runtime.
FROM python:3.11-slim
WORKDIR /app
COPY requirements.lock.txt pyproject.toml ./
COPY src ./src
COPY app ./app
COPY configs ./configs
RUN pip install --no-cache-dir -r requirements.lock.txt && pip install --no-cache-dir --no-deps -e ".[app]"
EXPOSE 8000 8501
CMD ["uvicorn", "terrasense.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
