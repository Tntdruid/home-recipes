FROM python:3.12-alpine

RUN apk add --no-cache tzdata

WORKDIR /app
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

ENV DATA_DIR=/data
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8099", "--log-level", "warning"]
