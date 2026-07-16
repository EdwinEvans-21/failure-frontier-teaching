FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN useradd --create-home --uid 10001 judge
WORKDIR /workspace
USER judge

ENTRYPOINT ["python", "-I", "/judge/harness.py"]

