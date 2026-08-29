#!/usr/bin/env bash
set -e

PORT=${PORT:-8000}
HOST=${HOST:-0.0.0.0}

echo "Starting Razorpay AI Revenue Recovery Agent on ${HOST}:${PORT}..."
exec uvicorn payment_recovery.service:app \
  --host "$HOST" \
  --port "$PORT"
