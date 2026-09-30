#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-.env}"
KEY_NAME="${2:-DJANGO_SECRET_KEY}"

command -v python3 >/dev/null 2>&1 || {
    echo "error: python3 is required" >&2
    exit 1
}

secret="$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')"

if [ -f "$ENV_FILE" ] && grep -q "^${KEY_NAME}=" "$ENV_FILE"; then
    tmp="$(mktemp)"
    sed "s|^${KEY_NAME}=.*|${KEY_NAME}=${secret}|" "$ENV_FILE" > "$tmp"
    mv "$tmp" "$ENV_FILE"
else
    printf '%s=%s\n' "$KEY_NAME" "$secret" >> "$ENV_FILE"
fi

echo "Wrote ${KEY_NAME} to ${ENV_FILE}"
