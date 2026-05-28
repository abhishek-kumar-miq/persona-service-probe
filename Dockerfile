FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml /app/
COPY probe /app/probe

RUN pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "probe.main"]
