#!/bin/sh
set -e

echo "等待数据库就绪并执行迁移..."
python manage.py migrate --noinput

if [ "${SEED_DEMO:-true}" = "true" ]; then
  echo "同步演示数据..."
  python manage.py seed_demo
fi

exec gunicorn app.wsgi:application --bind 0.0.0.0:8000 --workers 3
