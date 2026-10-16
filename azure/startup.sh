#!/usr/bin/env bash
set -e

export APP_ENV=production

exec gunicorn -w 2 -k gthread --threads 4 -b 0.0.0.0:${PORT:-8000} backend.app:app
