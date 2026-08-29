# syntax=docker/dockerfile:1
FROM python:3.11.15-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

FROM base AS test
COPY pyproject.toml README.md ./
COPY src ./src
COPY tests ./tests
COPY database ./database
COPY n8n-workflows ./n8n-workflows
COPY email-templates ./email-templates
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir '.[dev]'
CMD ["python", "-m", "pytest"]

FROM base AS runtime
RUN groupadd --system recovery && useradd --system --gid recovery recovery
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir .
USER recovery
EXPOSE 8000
CMD ["python", "-m", "payment_recovery"]
