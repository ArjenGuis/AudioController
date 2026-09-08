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
    # de app-gebruiker verschilt per locatie (wierden draait onder gergemwierden)
    u=$(docker exec "$NAME" cat /etc/testpi_user 2>/dev/null || echo pi)
    echo "export TEST_HOST=$u@127.0.0.1:$SSH_PORT"
    echo "export HTTP_PORT=$HTTP_PORT"
    echo "export BACKUP_DIR=$TEST_BACKUP_DIR"
    exit 0
fi

if [ "${1:-}" = "--no-audio" ]; then
    # Locaties die nog op de legacy pickle staan (noord, wierden) hebben bij het
    # starten nog geen JSON-config, dus daar kan enable_audio pas uit nadat de app
    # hem eenmaal gemigreerd heeft. Draai dit daarna, gevolgd door --restart.
    h=$(docker exec "$NAME" cat /etc/testpi_svchome 2>/dev/null || echo /root)
    docker exec -i -e CFGHOME="$h" "$NAME" python3 - <<'PYEOF'
import json, os
p = os.path.join(os.environ.get("CFGHOME", "/root"), ".audio_controller_settings.json")
try:
    d = json.load(open(p))
except FileNotFoundError:
    raise SystemExit("geen JSON-config gevonden in %s (draai eerst een update)" % os.path.dirname(p))
if d.get("settings", {}).get("enable_audio"):
    d["settings"]["enable_audio"] = False
    json.dump(d, open(p, "w"), indent=2)
    print("enable_audio uitgezet in %s" % p)
else:
    print("enable_audio stond al uit")
PYEOF
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

# Welke gebruiker draait de app? Op de meeste Pi's 'pi', op wierden 'gergemwierden'.
# Uit de unit van de backup halen, zodat de paden en de ssh-login kloppen.
APPUSER=pi
if [ -n "$LOC" ]; then
    if [ -n "$STAMP" ]; then B="$BACKUP_DIR/$LOC/$STAMP"; else
        B=$(ls -d "$BACKUP_DIR/$LOC"/*/ 2>/dev/null | sort | tail -1)
    fi
    if [ -n "$B" ] && [ -f "$B/audio_controller.service" ]; then
        wd=$(grep -E '^WorkingDirectory=' "$B/audio_controller.service" | head -1 | cut -d= -f2-)
        case "$wd" in /home/*) APPUSER=$(printf '%s' "$wd" | cut -d/ -f3) ;; esac
    fi
fi
if [ "$APPUSER" != "pi" ]; then
    echo "-- app-gebruiker is '$APPUSER' (uit de unit), wordt aangemaakt"
    docker exec "$NAME" bash -c "
        useradd -m -s /bin/bash '$APPUSER' 2>/dev/null || true
        echo '$APPUSER ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/'$APPUSER'
        mkdir -p /home/'$APPUSER'/.ssh && chown -R '$APPUSER':'$APPUSER' /home/'$APPUSER'/.ssh
        chmod 700 /home/'$APPUSER'/.ssh"
fi
docker exec "$NAME" bash -c "echo '$APPUSER' > /etc/testpi_user"
docker exec -i "$NAME" bash -c "cat > /home/$APPUSER/.ssh/authorized_keys && chown $APPUSER:$APPUSER /home/$APPUSER/.ssh/authorized_keys && chmod 600 /home/$APPUSER/.ssh/authorized_keys" < "$KEY.pub"

# de container maakt bij elke start nieuwe hostkeys
ssh-keygen -R "[127.0.0.1]:$SSH_PORT" >/dev/null 2>&1 || true
for _ in $(seq 1 15); do
    if ssh-keyscan -p "$SSH_PORT" -H 127.0.0.1 2>/dev/null | grep -q ssh; then break; fi
    sleep 1
done
ssh-keyscan -p "$SSH_PORT" -H 127.0.0.1 >> "$HOME/.ssh/known_hosts" 2>/dev/null

if [ -n "$LOC" ]; then
    [ -n "$B" ] && [ -d "$B" ] || { echo "Geen backup gevonden voor '$LOC' in $BACKUP_DIR"; exit 2; }
    echo "-- backup terugzetten: $B"
    APPDIR="/home/$APPUSER/AudioController"
    docker exec "$NAME" mkdir -p "$APPDIR"
    for f in audio_controller run_audio_controller.sh audio_controller.service audio_controller.html; do
        [ -e "$B/$f" ] && docker cp "$B/$f" "$NAME:$APPDIR/"
    done
    # De config hoort in de home van de SERVICE-user (User= in de unit, meestal root),
    # niet in die van de ssh-user.
    SVCUSER=root
    if [ -f "$B/audio_controller.service" ]; then
        u=$(grep -E '^User=' "$B/audio_controller.service" | head -1 | cut -d= -f2-)
        [ -n "$u" ] && SVCUSER=$u
    fi
    SVCHOME=$(docker exec "$NAME" getent passwd "$SVCUSER" | cut -d: -f6)
    [ -n "$SVCHOME" ] || SVCHOME=/root
    for f in .audio_controller_settings.json .audio_controller_cookie.txt \
             .audio_controller_users.txt .audio_controller_settings.pickle; do
        [ -f "$B/home/$f" ] && docker cp "$B/home/$f" "$NAME:$SVCHOME/$f"
    done
    docker exec "$NAME" bash -c "
        chown -R '$APPUSER':'$APPUSER' '$APPDIR'
        chmod 600 '$SVCHOME'/.audio_controller_* 2>/dev/null || true
        [ -f '$APPDIR/audio_controller.service' ] &&
            cp '$APPDIR/audio_controller.service' /etc/systemd/system/"
    docker exec "$NAME" bash -c "echo '$SVCHOME' > /etc/testpi_svchome"
    echo "   app in $APPDIR, config in $SVCHOME (service-user $SVCUSER)"

    # Zonder geluidskaart kan de app niet starten: set_routes zoekt een echt
    # opnameapparaat en valt om met KeyError: 'real_card'. Dan is er ook niets te
    # herstarten of te healthchecken. Daarom staat enable_audio hier standaard uit;
    # met WITH_AUDIO=1 laat je de config ongemoeid.
    if [ "${WITH_AUDIO:-0}" != "1" ]; then
        docker exec -i -e CFGHOME="$SVCHOME" "$NAME" python3 - <<'PYEOF'
import json, os
p = os.path.join(os.environ.get("CFGHOME", "/root"), ".audio_controller_settings.json")
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
