FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn odfpy
COPY src ./src
COPY apps ./apps
COPY data ./data
EXPOSE 8765
CMD ["python", "-m", "apps"]
