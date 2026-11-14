#!/bin/sh
# Har kuni PostgreSQL zaxira nusxasi (siqilgan), BACKUP_KEEP_DAYS kundan eskisi o'chiriladi.
# Tiklash:  gunzip -c backups/smartagro-YYYYMMDD-HHMM.sql.gz | docker compose exec -T db psql -U $POSTGRES_USER -d $POSTGRES_DB
set -eu
KEEP="${BACKUP_KEEP_DAYS:-14}"
mkdir -p /backups
while true; do
  STAMP=$(date +%Y%m%d-%H%M)
  if pg_dump --no-owner --format=plain | gzip > "/backups/smartagro-$STAMP.sql.gz.tmp"; then
    mv "/backups/smartagro-$STAMP.sql.gz.tmp" "/backups/smartagro-$STAMP.sql.gz"
    echo "backup ok: smartagro-$STAMP.sql.gz"
  else
    echo "backup FAILED at $STAMP" >&2
    rm -f "/backups/smartagro-$STAMP.sql.gz.tmp"
  fi
  find /backups -name 'smartagro-*.sql.gz' -mtime +"$KEEP" -delete
  sleep 86400
done
