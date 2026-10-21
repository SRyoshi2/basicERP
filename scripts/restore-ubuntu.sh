#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
ENV_PATH="${PROJECT_ROOT}/.env"
BACKUP_DIRECTORY=""
PROJECT_NAME=""
CONFIRM_RESTORE="false"
SKIP_SAFETY_BACKUP="false"
NO_START="false"

usage() {
  cat <<'EOF'
Verwendung: ./scripts/restore-ubuntu.sh --backup VERZEICHNIS [Optionen]

  --project-name NAME     Abweichendes Compose-Projekt, z. B. fuer einen Restore-Test
  --confirm-restore       Destruktiven Restore ohne Eingabe von RESTORE bestaetigen
  --skip-safety-backup    Nur fuer isolierte Testprojekte; kein Vorab-Backup erstellen
  --no-start              Dienste nach Restore nicht komplett starten
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backup) BACKUP_DIRECTORY="${2:?Wert fuer --backup fehlt}"; shift 2 ;;
    --project-name) PROJECT_NAME="${2:?Wert fuer --project-name fehlt}"; shift 2 ;;
    --confirm-restore) CONFIRM_RESTORE="true"; shift ;;
    --skip-safety-backup) SKIP_SAFETY_BACKUP="true"; shift ;;
    --no-start) NO_START="true"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'Unbekannte Option: %s\n' "$1" >&2; usage; exit 2 ;;
  esac
done

[[ -f "$ENV_PATH" ]] || { printf '.env fehlt. Bitte basicERP zuerst installieren.\n' >&2; exit 1; }
[[ -n "$BACKUP_DIRECTORY" ]] || { usage; exit 2; }
BACKUP_DIRECTORY="$(cd -- "$BACKUP_DIRECTORY" && pwd)"
for file in database.dump archive.tar.gz media.tar.gz SHA256SUMS manifest.json; do
  [[ -f "${BACKUP_DIRECTORY}/${file}" ]] || { printf 'Backup ist unvollstaendig: %s fehlt.\n' "$file" >&2; exit 1; }
done
(cd "$BACKUP_DIRECTORY" && sha256sum --check SHA256SUMS)

PROJECT_NAME="${PROJECT_NAME:-$(sed -n 's/^COMPOSE_PROJECT_NAME=//p' "$ENV_PATH" | head -n 1)}"
DATABASE_NAME="$(sed -n 's/^POSTGRES_DB=//p' "$ENV_PATH" | head -n 1)"
DATABASE_USER="$(sed -n 's/^POSTGRES_USER=//p' "$ENV_PATH" | head -n 1)"
[[ "$PROJECT_NAME" =~ ^[a-z0-9][a-z0-9_-]*$ ]] || { printf 'Ungueltiger Docker-Projektname.\n' >&2; exit 2; }
[[ "$DATABASE_NAME" =~ ^[A-Za-z_][A-Za-z0-9_]*$ && "$DATABASE_USER" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || { printf 'Ungueltige Datenbankkonfiguration.\n' >&2; exit 2; }

if [[ "$CONFIRM_RESTORE" != "true" ]]; then
  read -r -p "RESTORE eingeben, um Projekt '${PROJECT_NAME}' zu ueberschreiben: " answer
  [[ "$answer" == "RESTORE" ]] || { printf 'Wiederherstellung abgebrochen.\n' >&2; exit 1; }
fi

COMPOSE=(docker compose --env-file "$ENV_PATH" --project-name "$PROJECT_NAME")
cd "$PROJECT_ROOT"
if [[ "$SKIP_SAFETY_BACKUP" != "true" ]]; then
  SAFETY_PATH="${PROJECT_ROOT}/backups/pre-restore-$(date +%Y%m%d-%H%M%S)"
  "${SCRIPT_DIR}/backup-ubuntu.sh" --output "$SAFETY_PATH" --project-name "$PROJECT_NAME"
fi

"${COMPOSE[@]}" stop web worker nginx >/dev/null 2>&1 || true
"${COMPOSE[@]}" up -d --wait db
"${COMPOSE[@]}" cp "${BACKUP_DIRECTORY}/database.dump" db:/tmp/basicerp-restore.dump
"${COMPOSE[@]}" exec -T db sh -c 'dropdb -U "$POSTGRES_USER" --maintenance-db=postgres --if-exists "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" -O "$POSTGRES_USER" "$POSTGRES_DB" && pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner /tmp/basicerp-restore.dump && rm -f /tmp/basicerp-restore.dump'

"${COMPOSE[@]}" run --rm --no-deps --volume "${BACKUP_DIRECTORY}:/restore:ro" web sh -c 'find /app/archive -mindepth 1 -delete && find /app/media -mindepth 1 -delete && tar -C /app/archive -xzf /restore/archive.tar.gz && tar -C /app/media -xzf /restore/media.tar.gz'
"${COMPOSE[@]}" run --rm web python manage.py migrate --noinput
"${COMPOSE[@]}" run --rm web python manage.py check

if [[ "$NO_START" != "true" ]]; then
  "${COMPOSE[@]}" up -d
fi
printf "Restore erfolgreich fuer Projekt '%s'.\n" "$PROJECT_NAME"
