#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
ENV_PATH="${PROJECT_ROOT}/.env"
OUTPUT_DIRECTORY=""
PROJECT_NAME=""

usage() {
  cat <<'EOF'
Verwendung: ./scripts/backup-ubuntu.sh [--output VERZEICHNIS] [--project-name NAME]

Sichert PostgreSQL, Archiv und Medien inklusive SHA-256-Pruefsummen.
Die .env mit Geheimnissen ist bewusst nicht Bestandteil des Backups.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output) OUTPUT_DIRECTORY="${2:?Wert fuer --output fehlt}"; shift 2 ;;
    --project-name) PROJECT_NAME="${2:?Wert fuer --project-name fehlt}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'Unbekannte Option: %s\n' "$1" >&2; usage; exit 2 ;;
  esac
done

[[ -f "$ENV_PATH" ]] || { printf '.env fehlt. Bitte basicERP zuerst installieren.\n' >&2; exit 1; }
command -v docker >/dev/null 2>&1 || { printf 'Docker wurde nicht gefunden.\n' >&2; exit 1; }
PROJECT_NAME="${PROJECT_NAME:-$(sed -n 's/^COMPOSE_PROJECT_NAME=//p' "$ENV_PATH" | head -n 1)}"
[[ "$PROJECT_NAME" =~ ^[a-z0-9][a-z0-9_-]*$ ]] || { printf 'Ungueltiger Docker-Projektname.\n' >&2; exit 2; }

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
OUTPUT_DIRECTORY="${OUTPUT_DIRECTORY:-${PROJECT_ROOT}/backups/basicerp-${TIMESTAMP}}"
[[ ! -e "$OUTPUT_DIRECTORY" ]] || { printf 'Ziel existiert bereits: %s\n' "$OUTPUT_DIRECTORY" >&2; exit 1; }
mkdir -p "$OUTPUT_DIRECTORY"
OUTPUT_DIRECTORY="$(cd -- "$OUTPUT_DIRECTORY" && pwd)"
REMOTE_PREFIX="/tmp/basicerp-backup-${TIMESTAMP}"
COMPOSE=(docker compose --env-file "$ENV_PATH" --project-name "$PROJECT_NAME")
SERVICES_TO_RESTART=()

restart_services() {
  if (( ${#SERVICES_TO_RESTART[@]} > 0 )); then
    "${COMPOSE[@]}" up -d "${SERVICES_TO_RESTART[@]}"
  fi
}
trap restart_services EXIT

cd "$PROJECT_ROOT"
"${COMPOSE[@]}" up -d --wait db
mapfile -t RUNNING_SERVICES < <("${COMPOSE[@]}" ps --services --status running)
for service in web worker beat nginx; do
  for running in "${RUNNING_SERVICES[@]}"; do
    if [[ "$service" == "$running" ]]; then SERVICES_TO_RESTART+=("$service"); fi
  done
done
if (( ${#SERVICES_TO_RESTART[@]} > 0 )); then
  "${COMPOSE[@]}" stop "${SERVICES_TO_RESTART[@]}"
fi
"${COMPOSE[@]}" exec -T db sh -c "pg_dump -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" --format=custom --file=${REMOTE_PREFIX}.dump"
"${COMPOSE[@]}" cp "db:${REMOTE_PREFIX}.dump" "${OUTPUT_DIRECTORY}/database.dump"

"${COMPOSE[@]}" run --rm --no-deps web sh -c 'tar -C /app/archive -czf /tmp/archive.tar.gz . && tar -C /app/media -czf /tmp/media.tar.gz . && cp /tmp/archive.tar.gz /tmp/media.tar.gz /app/media/'
"${COMPOSE[@]}" cp web:/app/media/archive.tar.gz "${OUTPUT_DIRECTORY}/archive.tar.gz"
"${COMPOSE[@]}" cp web:/app/media/media.tar.gz "${OUTPUT_DIRECTORY}/media.tar.gz"
"${COMPOSE[@]}" run --rm --no-deps web sh -c 'rm -f /app/media/archive.tar.gz /app/media/media.tar.gz'
"${COMPOSE[@]}" exec -T db rm -f "${REMOTE_PREFIX}.dump"

(
  cd "$OUTPUT_DIRECTORY"
  sha256sum database.dump archive.tar.gz media.tar.gz > SHA256SUMS
)
cat >"${OUTPUT_DIRECTORY}/manifest.json" <<EOF
{
  "schema_version": 1,
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "source_project": "${PROJECT_NAME}",
  "includes": ["PostgreSQL", "Archiv", "Medien"],
  "excludes": [".env", "Redis-Warteschlange"]
}
EOF
chmod -R go-rwx "$OUTPUT_DIRECTORY"
printf 'Backup erfolgreich: %s\n' "$OUTPUT_DIRECTORY"
printf 'WARNUNG: Die .env ist nicht enthalten und muss separat sicher verwahrt werden.\n' >&2
restart_services
SERVICES_TO_RESTART=()
trap - EXIT
