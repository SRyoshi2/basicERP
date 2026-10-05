#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
ENV_PATH="${PROJECT_ROOT}/.env"

DOMAIN=""
HTTP_PORT=""
PROJECT_NAME=""
BEHIND_HTTPS_PROXY="false"
NON_INTERACTIVE="false"
FORCE="false"

usage() {
  cat <<'EOF'
Verwendung: ./scripts/install-ubuntu.sh [Optionen]

  --domain NAME          Domain/Hostname ohne Protokoll
  --http-port PORT       Lokaler Port (Standard: 8080)
  --project-name NAME    Docker-Compose-Projektname
  --behind-https-proxy   Öffentliche URL verwendet HTTPS; TLS endet im Reverse Proxy
  --non-interactive      Keine Rückfragen; Standardwerte verwenden
  --force                Vorhandene .env bewusst überschreiben
  -h, --help             Hilfe anzeigen
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain) DOMAIN="${2:?Wert für --domain fehlt}"; shift 2 ;;
    --http-port) HTTP_PORT="${2:?Wert für --http-port fehlt}"; shift 2 ;;
    --project-name) PROJECT_NAME="${2:?Wert für --project-name fehlt}"; shift 2 ;;
    --behind-https-proxy) BEHIND_HTTPS_PROXY="true"; shift ;;
    --non-interactive) NON_INTERACTIVE="true"; shift ;;
    --force) FORCE="true"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'Unbekannte Option: %s\n' "$1" >&2; usage; exit 2 ;;
  esac
done

read_setting() {
  local prompt="$1"
  local current="$2"
  local default="$3"
  local answer=""

  if [[ -n "$current" ]]; then printf '%s' "$current"; return; fi
  if [[ "$NON_INTERACTIVE" == "true" ]]; then printf '%s' "$default"; return; fi
  read -r -p "${prompt} [${default}]: " answer
  printf '%s' "${answer:-$default}"
}

command_required() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf "Fehlender Befehl: %s\n" "$1" >&2
    exit 1
  fi
}

env_value() {
  local key="$1"
  sed -n "s/^${key}=//p" "$ENV_PATH" | head -n 1
}

docker_build_with_retry() {
  local attempt
  for attempt in 1 2 3; do
    if docker compose --env-file "$ENV_PATH" build; then return 0; fi
    if (( attempt < 3 )); then
      local delay=$((attempt * 5))
      printf 'WARNUNG: Docker-Build fehlgeschlagen (Versuch %s/3). Neuer Versuch in %s Sekunden.\n' "$attempt" "$delay" >&2
      sleep "$delay"
    fi
  done
  printf 'Docker-Build ist nach drei Versuchen fehlgeschlagen.\n' >&2
  return 1
}

start_docker_infrastructure() {
  local attempt
  for attempt in 1 2 3; do
    if docker compose --env-file "$ENV_PATH" up -d db redis; then return 0; fi
    if (( attempt < 3 )); then
      local delay=$((attempt * 5))
      printf 'WARNUNG: PostgreSQL/Redis-Start fehlgeschlagen (Versuch %s/3). Neuer Versuch in %s Sekunden.\n' "$attempt" "$delay" >&2
      sleep "$delay"
    fi
  done
  printf 'PostgreSQL/Redis konnten nach drei Versuchen nicht gestartet werden.\n' >&2
  return 1
}

REUSE_EXISTING_ENV="false"
if [[ -e "$ENV_PATH" && "$FORCE" == "false" ]]; then
  REUSE_EXISTING_ENV="true"
  DOMAIN="$(env_value APP_DOMAIN)"
  HTTP_PORT="$(env_value APP_HTTP_PORT)"
  PROJECT_NAME="$(env_value COMPOSE_PROJECT_NAME)"
  PUBLIC_SCHEME_FROM_ENV="$(env_value APP_PUBLIC_SCHEME)"
  if [[ -z "$DOMAIN" || -z "$HTTP_PORT" || -z "$PROJECT_NAME" || -z "$PUBLIC_SCHEME_FROM_ENV" ]]; then
    printf 'Die bestehende .env ist unvollständig. Mit --force neu erzeugen.\n' >&2
    exit 1
  fi
  if [[ "$PUBLIC_SCHEME_FROM_ENV" == "https" ]]; then BEHIND_HTTPS_PROXY="true"; fi
  printf 'Bestehende .env wird für die Wiederaufnahme verwendet.\n'
else
  DOMAIN="$(read_setting "Domain oder Hostname (ohne Protokoll/Pfad)" "$DOMAIN" "localhost")"
  HTTP_PORT="$(read_setting "Lokaler HTTP-Port" "$HTTP_PORT" "8080")"
  PROJECT_NAME="$(read_setting "Docker-Projektname" "$PROJECT_NAME" "basicerp")"

  if [[ "$NON_INTERACTIVE" == "false" && "$BEHIND_HTTPS_PROXY" == "false" ]]; then
    read -r -p "Wird basicERP hinter einem externen HTTPS-Reverse-Proxy betrieben? [j/N]: " proxy_answer
    if [[ "$proxy_answer" =~ ^(j|ja|y|yes)$ ]]; then BEHIND_HTTPS_PROXY="true"; fi
  fi
fi

if [[ "$DOMAIN" =~ ://|/|[[:space:]] ]]; then
  printf 'Die Domain darf kein Protokoll, keinen Pfad und keine Leerzeichen enthalten.\n' >&2
  exit 2
fi
if [[ ! "$HTTP_PORT" =~ ^[0-9]+$ ]] || (( HTTP_PORT < 1 || HTTP_PORT > 65535 )); then
  printf 'Der HTTP-Port muss zwischen 1 und 65535 liegen.\n' >&2
  exit 2
fi
if [[ ! "$PROJECT_NAME" =~ ^[a-z0-9][a-z0-9_-]*$ ]]; then
  printf 'Der Docker-Projektname ist ungültig.\n' >&2
  exit 2
fi

command_required docker
command_required openssl
command_required curl
if ! docker compose version >/dev/null 2>&1; then
  printf 'Docker Compose Plugin fehlt. Unter Ubuntu das Paket docker-compose-plugin installieren.\n' >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  printf 'Docker Engine läuft nicht oder der aktuelle Benutzer hat keinen Zugriff.\n' >&2
  printf 'Prüfe: sudo systemctl start docker; danach ggf. neu anmelden, wenn die docker-Gruppe geändert wurde.\n' >&2
  exit 1
fi

if [[ "$BEHIND_HTTPS_PROXY" == "true" ]]; then
  PUBLIC_SCHEME="https"
  PUBLIC_ORIGIN="https://${DOMAIN}"
elif [[ "$HTTP_PORT" == "80" ]]; then
  PUBLIC_SCHEME="http"
  PUBLIC_ORIGIN="http://${DOMAIN}"
else
  PUBLIC_SCHEME="http"
  PUBLIC_ORIGIN="http://${DOMAIN}:${HTTP_PORT}"
fi

if [[ "$REUSE_EXISTING_ENV" == "false" ]]; then
  DJANGO_SECRET="$(openssl rand -hex 48)"
  DB_PASSWORD="$(openssl rand -hex 24)"
  ALLOWED_HOSTS="${DOMAIN},localhost,127.0.0.1"

  umask 077
  cat >"$ENV_PATH" <<EOF
COMPOSE_PROJECT_NAME=${PROJECT_NAME}
APP_DOMAIN=${DOMAIN}
APP_PUBLIC_SCHEME=${PUBLIC_SCHEME}
APP_HTTP_PORT=${HTTP_PORT}
APP_TIME_ZONE=Europe/Berlin
DJANGO_SECRET_KEY=${DJANGO_SECRET}
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=${ALLOWED_HOSTS}
CSRF_TRUSTED_ORIGINS=${PUBLIC_ORIGIN}
POSTGRES_DB=basicerp
POSTGRES_USER=basicerp
POSTGRES_PASSWORD=${DB_PASSWORD}
DATABASE_URL=postgresql://basicerp:${DB_PASSWORD}@db:5432/basicerp
REDIS_URL=redis://redis:6379/0
EOF
  printf '\n.env wurde mit zufälligen Secrets angelegt.\n'
fi

cd "$PROJECT_ROOT"
docker compose --env-file "$ENV_PATH" config --quiet

printf 'Container-Images werden gebaut …\n'
docker_build_with_retry
start_docker_infrastructure

printf 'Datenbankmigrationen werden ausgeführt …\n'
docker compose --env-file "$ENV_PATH" run --rm web python manage.py migrate --noinput

if [[ "$DOMAIN" == "localhost" ]]; then
  ADMIN_EMAIL="admin@localhost.invalid"
else
  ADMIN_EMAIL="admin@${DOMAIN}"
fi

docker compose --env-file "$ENV_PATH" run --rm \
  -e INITIAL_ADMIN_USERNAME=admin \
  -e INITIAL_ADMIN_PASSWORD=admin \
  -e "INITIAL_ADMIN_EMAIL=${ADMIN_EMAIL}" \
  web python manage.py bootstrap_admin

docker compose --env-file "$ENV_PATH" up -d

LOCAL_URL="http://localhost:${HTTP_PORT}"
printf 'Warte auf den Healthcheck …\n'
READY="false"
for _attempt in $(seq 1 30); do
  if curl --fail --silent --show-error "${LOCAL_URL}/api/v1/health/ready/" >/dev/null 2>&1; then
    READY="true"
    break
  fi
  sleep 2
done

if [[ "$READY" != "true" ]]; then
  printf 'WARNUNG: Healthcheck ist noch nicht bereit. Diagnose: docker compose logs --tail 100\n' >&2
fi

cat <<EOF

basicERP ist eingerichtet.
Lokal:      ${LOCAL_URL}
Öffentlich: ${PUBLIC_ORIGIN}
Benutzer:   admin
Passwort:   admin

WARNUNG: Das Installationspasswort ist öffentlich bekannt. Die Anwendung erzwingt
nach der ersten Anmeldung einen Passwortwechsel.

Fahrplan/Testhilfe: ${LOCAL_URL}/roadmap/
EOF

if [[ "$BEHIND_HTTPS_PROXY" == "true" ]]; then
  printf 'WARNUNG: HTTPS muss im externen Reverse Proxy auf localhost:%s weitergeleitet werden.\n' "$HTTP_PORT"
fi
