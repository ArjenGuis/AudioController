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

# Een gebruikersnaam uit een backup mag nooit klakkeloos in een shell-commando: die
# naam komt uit het audio_controller.service-bestand van een andere machine. Een
# apostrof erin zou uit de quoting breken en als root in de container draaien.
# Daarom: eerst valideren, en verderop alles als ARGUMENT doorgeven in plaats van
# interpoleren.
geldige_naam() {
    case "$1" in
        ''|*[!a-z0-9_-]*) return 1 ;;
        [!a-z_]*) return 1 ;;
        *) [ ${#1} -le 32 ] ;;
    esac
}

# Welke gebruiker draait de app? Op de meeste Pi's 'pi', op wierden 'gergemwierden'.
# Uit de unit van de backup halen, zodat de paden en de ssh-login kloppen.
APPUSER=pi
if [ -n "$LOC" ]; then
    if [ -n "$STAMP" ]; then B="$BACKUP_DIR/$LOC/$STAMP"; else
        B=$(ls -d "$BACKUP_DIR/$LOC"/*/ 2>/dev/null | sort | tail -1)
    fi
    if [ -n "$B" ] && [ -f "$B/audio_controller.service" ]; then
        wd=$(grep -E '^WorkingDirectory=' "$B/audio_controller.service" | head -1 | cut -d= -f2-)
        case "$wd" in /home/*) kandidaat=$(printf '%s' "$wd" | cut -d/ -f3) ;; *) kandidaat="" ;; esac
        if [ -n "$kandidaat" ]; then
            geldige_naam "$kandidaat" || {
                echo "Onbruikbare gebruikersnaam in $B/audio_controller.service: '$kandidaat'" >&2
                exit 2
            }
            APPUSER=$kandidaat
        fi
    fi
fi
if [ "$APPUSER" != "pi" ]; then
    echo "-- app-gebruiker is '$APPUSER' (uit de unit), wordt aangemaakt"
    docker exec -i "$NAME" bash -s -- "$APPUSER" <<'EOSH'
set -e
u=$1
useradd -m -s /bin/bash "$u" 2>/dev/null || true
printf '%s ALL=(ALL) NOPASSWD:ALL\n' "$u" > "/etc/sudoers.d/$u"
mkdir -p "/home/$u/.ssh"
chown -R "$u:$u" "/home/$u/.ssh"
chmod 700 "/home/$u/.ssh"
EOSH
fi
docker exec -i "$NAME" bash -s -- "$APPUSER" <<'EOSH'
printf '%s\n' "$1" > /etc/testpi_user
EOSH
docker exec -i "$NAME" bash -c 'u=$1; cat > "/home/$u/.ssh/authorized_keys" && chown "$u:$u" "/home/$u/.ssh/authorized_keys" && chmod 600 "/home/$u/.ssh/authorized_keys"' _ "$APPUSER" < "$KEY.pub"

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
        if [ -n "$u" ]; then
            # ook deze naam komt uit een bestand van een andere machine
            geldige_naam "$u" || {
                echo "Onbruikbare service-user in $B/audio_controller.service: '$u'" >&2
                exit 2
            }
            SVCUSER=$u
        fi
    fi
    SVCHOME=$(docker exec "$NAME" getent passwd "$SVCUSER" | cut -d: -f6)
    case "$SVCHOME" in /*) ;; *) SVCHOME=/root ;; esac
    for f in .audio_controller_settings.json .audio_controller_cookie.txt \
             .audio_controller_users.txt .audio_controller_settings.pickle; do
        [ -f "$B/home/$f" ] && docker cp "$B/home/$f" "$NAME:$SVCHOME/$f"
    done
    docker exec -i "$NAME" bash -s -- "$APPUSER" "$APPDIR" "$SVCHOME" <<'EOSH'
u=$1; appdir=$2; svchome=$3
chown -R "$u:$u" "$appdir"
chmod 600 "$svchome"/.audio_controller_* 2>/dev/null || true
[ -f "$appdir/audio_controller.service" ] &&
    cp "$appdir/audio_controller.service" /etc/systemd/system/
printf '%s\n' "$svchome" > /etc/testpi_svchome
EOSH
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
