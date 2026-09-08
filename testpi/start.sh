#!/bin/bash
# testpi/start.sh - zet een lokale nabootsing van een Pi op, zodat update_pi.sh
# volledig getest kan worden zonder een kerk-Pi aan te raken.
#
# Gebruik:
#   ./testpi/start.sh                     lege Pi (verse installatie)
#   ./testpi/start.sh west                nieuwste backup van west erin zetten
#   ./testpi/start.sh west 20260908_205736    een specifieke backup
#   ./testpi/start.sh --stop              container weghalen
#
# Daarna:
#   eval "$(./testpi/start.sh --env)"     zet TEST_HOST/HTTP_PORT/BACKUP_DIR
#   ./update_pi.sh west --status
#   ./update_pi.sh west --dry-run --yes
#   ./update_pi.sh west --yes
#   ./update_pi.sh west --rollback --yes
#
# De container draait armv7l met Python 3.7.3, net als west (Raspbian buster).
# systemd draait niet in een container; systemctl/journalctl zijn vervangen door
# shims die precies de opdrachten kennen die update_pi.sh gebruikt. Alles daar
# omheen -- ssh, rsync, sudo, de venv, pip install, backup en rollback -- is echt.
set -eo pipefail
cd "$(dirname "$0")/.."

NAME=testpi
IMAGE=audiocontroller-testpi:buster
SSH_PORT="${TESTPI_SSH_PORT:-2223}"
HTTP_PORT="${TESTPI_HTTP_PORT:-18080}"
INT_PORT="${TESTPI_INT_PORT:-15000}"
KEY="${KEY:-$HOME/.ssh/rpi_ed25519}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/AudioController_pi_backups}"
TEST_BACKUP_DIR="${TESTPI_BACKUP_DIR:-/tmp/testpi_backups}"

if [ "${1:-}" = "--env" ]; then
    echo "export TEST_HOST=pi@127.0.0.1:$SSH_PORT"
    echo "export HTTP_PORT=$HTTP_PORT"
    echo "export BACKUP_DIR=$TEST_BACKUP_DIR"
    exit 0
fi

if [ "${1:-}" = "--stop" ]; then
    docker rm -f "$NAME" >/dev/null 2>&1 && echo "container '$NAME' verwijderd" || echo "geen container '$NAME'"
    ssh-keygen -R "[127.0.0.1]:$SSH_PORT" >/dev/null 2>&1 || true
    exit 0
fi

LOC="${1:-}"
STAMP="${2:-}"

[ -f "$KEY.pub" ] || { echo "Publieke sleutel niet gevonden: $KEY.pub (zet KEY=...)"; exit 2; }

echo "-- image bouwen ($IMAGE, linux/arm/v7 zoals west)"
docker build --platform linux/arm/v7 -t "$IMAGE" testpi/ >/dev/null

echo "-- container starten (ssh :$SSH_PORT, extern :$HTTP_PORT, intern :$INT_PORT)"
docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" --platform linux/arm/v7 \
    -p "$SSH_PORT:22" -p "$HTTP_PORT:8080" -p "$INT_PORT:5000" "$IMAGE" >/dev/null
sleep 4

docker exec -i "$NAME" bash -c 'cat > /home/pi/.ssh/authorized_keys && chown pi:pi /home/pi/.ssh/authorized_keys && chmod 600 /home/pi/.ssh/authorized_keys' < "$KEY.pub"

# de container maakt bij elke start nieuwe hostkeys
ssh-keygen -R "[127.0.0.1]:$SSH_PORT" >/dev/null 2>&1 || true
for _ in $(seq 1 15); do
    if ssh-keyscan -p "$SSH_PORT" -H 127.0.0.1 2>/dev/null | grep -q ssh; then break; fi
    sleep 1
done
ssh-keyscan -p "$SSH_PORT" -H 127.0.0.1 >> "$HOME/.ssh/known_hosts" 2>/dev/null

if [ -n "$LOC" ]; then
    if [ -n "$STAMP" ]; then B="$BACKUP_DIR/$LOC/$STAMP"; else
        B=$(ls -d "$BACKUP_DIR/$LOC"/*/ 2>/dev/null | sort | tail -1)
    fi
    [ -n "$B" ] && [ -d "$B" ] || { echo "Geen backup gevonden voor '$LOC' in $BACKUP_DIR"; exit 2; }
    echo "-- backup terugzetten: $B"
    docker exec "$NAME" mkdir -p /home/pi/AudioController
    for f in audio_controller run_audio_controller.sh audio_controller.service audio_controller.html; do
        [ -e "$B/$f" ] && docker cp "$B/$f" "$NAME:/home/pi/AudioController/"
    done
    for f in .audio_controller_settings.json .audio_controller_cookie.txt \
             .audio_controller_users.txt .audio_controller_settings.pickle; do
        [ -f "$B/home/$f" ] && docker cp "$B/home/$f" "$NAME:/root/$f"
    done
    docker exec "$NAME" bash -c '
        chown -R pi:pi /home/pi/AudioController
        chmod 600 /root/.audio_controller_* 2>/dev/null || true
        [ -f /home/pi/AudioController/audio_controller.service ] &&
            cp /home/pi/AudioController/audio_controller.service /etc/systemd/system/'

    # Zonder geluidskaart kan de app niet starten: set_routes zoekt een echt
    # opnameapparaat en valt om met KeyError: 'real_card'. Dan is er ook niets te
    # herstarten of te healthchecken. Daarom staat enable_audio hier standaard uit;
    # met WITH_AUDIO=1 laat je de config ongemoeid.
    if [ "${WITH_AUDIO:-0}" != "1" ]; then
        docker exec -i "$NAME" python3 - <<'PYEOF'
import json
p = "/root/.audio_controller_settings.json"
try:
    d = json.load(open(p))
    if d.get("settings", {}).get("enable_audio"):
        d["settings"]["enable_audio"] = False
        json.dump(d, open(p, "w"), indent=2)
        print("   enable_audio uitgezet (geen geluidskaart in een container; WITH_AUDIO=1 om dit te laten staan)")
except FileNotFoundError:
    pass
PYEOF
    fi
fi

mkdir -p "$TEST_BACKUP_DIR"

echo
echo "klaar. De testpi draait: $(docker exec "$NAME" bash -c 'uname -m; python3 -V' | tr '\n' ' ')"
echo
echo "Zet de omgeving en test:"
echo "  eval \"\$(./testpi/start.sh --env)\""
echo "  ./update_pi.sh ${LOC:-west} --status"
echo "  ./update_pi.sh ${LOC:-west} --dry-run --yes"
echo "  ./update_pi.sh ${LOC:-west} --yes"
echo
echo "Opruimen: ./testpi/start.sh --stop"
