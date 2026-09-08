# testpi — een Pi nabootsen om `update_pi.sh` te testen

Een deploy naar een kerk-Pi is niet vrijblijvend: die draait live diensten. Met dit
mapje zet je in één commando een lokale nabootsing op, zet je er een echte backup van
een locatie in, en draai je daar de hele update op. Zo weet je vóór een uitrol dat het
script doet wat het moet doen.

## Snel

```bash
./testpi/start.sh west          # bouwt + start de container, zet de nieuwste west-backup erin
eval "$(./testpi/start.sh --env)"   # zet TEST_HOST, HTTP_PORT en BACKUP_DIR

./update_pi.sh west --status
./update_pi.sh west --dry-run --yes
./update_pi.sh west --yes
./update_pi.sh west --rollback --yes

./testpi/start.sh --stop        # opruimen
```

Zonder locatie (`./testpi/start.sh`) krijg je een lege Pi — handig om een verse
installatie te testen.

Reken op enkele minuten voor de eerste `--yes` in een verse container: armv7 draait
onder emulatie en `pip install` moet de hele venv opbouwen. Een tweede update in
dezelfde container is snel, want dan staat de venv er al — net als op een echte Pi.

## Waarom dit realistisch genoeg is

De container is **armv7l met Python 3.7.3**, precies zoals west (Raspbian buster).
Dat is geen detail: `pip install` haalt op armv7 andere wheels dan op arm64 of x86,
en pakketten zonder wheel worden daar vanaf broncode gebouwd. Juist dát is wat een
deploy op een Pi kan laten stranden, en dat wordt hier dus echt getest.

Echt in deze opzet: ssh, rsync, sudo, de venv, `pip install --editable`, de
pre-deploy backup, de sync van package/scripts/kiosk-launcher, en de rollback.

## Wat niet echt is

**systemd draait niet in een container.** `systemctl` en `journalctl` zijn vervangen
door shims (`testpi/systemctl`, `testpi/journalctl`) die precies de opdrachten kennen
die `update_pi.sh` gebruikt: `start`/`stop`/`restart`/`is-active`/`status`,
`show -p User --value`, `show -p ActiveEnterTimestamp --value`, `daemon-reload`,
`enable`, en `journalctl -u <unit> -n <N>`. De unit wordt echt gelezen: `ExecStart`,
`WorkingDirectory` en `User` komen uit `/etc/systemd/system/audio_controller.service`,
dus de app start als root met de config in `/root/`, net als op de Pi.

Wat de shim dus **niet** dekt: `Restart=always`, opstarten bij boot, en de precieze
timing van systemd. Dat blijft iets om op de Pi zelf te controleren.

Verder ontbreken de hardware-afhankelijkheden: geen ITEC op `/dev/ttyUSB0`, geen
ALSA/ffmpeg-audio, geen GPIO en geen camera's. De app meldt "Cannot open serial port"
en "GPIO disabled" — dat is hier normaal.

Zonder geluidskaart kan de app zelfs helemaal niet starten: `set_routes` zoekt een echt
opnameapparaat en valt om met `KeyError: 'real_card'`. Dan valt er ook niets te
herstarten of te healthchecken. `start.sh` zet daarom in de teruggezette config
`enable_audio=false`. Wil je de config precies laten zoals hij op de Pi staat, gebruik
dan `WITH_AUDIO=1 ./testpi/start.sh west` — de app start dan niet, maar je ziet wel wat
er op een Pi zonder (of met een hernummerde) geluidskaart zou gebeuren.

## Wat deze opstelling al gevonden heeft

- **`lxml` was ongepind** en kwam via `onvif-zeep` → `zeep` binnen. Op armv7/Python 3.7
  heeft piwheels wheels tot en met 5.2.x; daarboven bouwt pip vanaf broncode en strandt
  op ontbrekende `libxml2`/`libxslt`-dev-pakketten. Bestaande Pi's merkten dat niet
  (daar staat 5.2.2 al), maar een **verse** installatie zou stuklopen. Nu `lxml<5.3` in
  `setup.py`.
- De healthcheck toonde `-> 000000` (curl schrijft zelf al `000`, en er stond nog een
  `|| echo 000` achter), en `--status` toonde `python:   line` als de venv ontbrak.
  Allebei gefixt in `update_pi.sh`.

## Poorten

| | container | host | reden |
|---|---|---|---|
| ssh | 22 | 2223 | 2222 kan in gebruik zijn |
| extern (app) | 8080 | 18080 | 8080 is vaak al bezet |
| intern (app) | 5000 | 15000 | |

De healthcheck van `update_pi.sh` gebruikt standaard poort 8080; daarvoor is
`HTTP_PORT=` toegevoegd, en `--env` zet die goed. Aanpassen kan met
`TESTPI_SSH_PORT` / `TESTPI_HTTP_PORT` / `TESTPI_INT_PORT`.

## Let op

- `--env` zet ook `BACKUP_DIR=/tmp/testpi_backups`, zodat de backups die het script
  tijdens het testen maakt **niet** tussen je echte Pi-backups terechtkomen.
- De backup die je erin zet bevat credentials (cookie-geheim, gebruikers,
  camera-wachtwoorden, icecast-URL). Die staan alleen in de draaiende container, niet
  in het image. Ruim op met `./testpi/start.sh --stop` als je klaar bent.
- Je publieke sleutel (`~/.ssh/rpi_ed25519.pub`, of `KEY=`) wordt bij het starten in de
  container gezet en zit bewust niet in het image.
- De container krijgt bij elke start nieuwe hostkeys; `start.sh` werkt je
  `known_hosts` daarom bij en `--stop` haalt de regel er weer uit.
