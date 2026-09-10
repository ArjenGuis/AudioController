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

Werkt voor elke locatie. De app-gebruiker en de service-gebruiker worden uit de
`audio_controller.service` van de backup gelezen, dus wierden (die onder
`gergemwierden` draait in plaats van `pi`) komt vanzelf goed terecht, met de config
in de home van de service-user.

**Staat de locatie nog op de legacy pickle** (noord en wierden, west niet), dan is er
bij het starten nog geen JSON-config en kan `enable_audio` pas ná de eerste migratie
uit. De update laat de app dan één keer omvallen op de ontbrekende geluidskaart;
daarna:

```bash
./testpi/start.sh --no-audio
./update_pi.sh noord --restart --yes
```

Reken op enkele minuten voor de eerste `--yes` in een verse container: armv7 draait
onder emulatie en `pip install` moet de hele venv opbouwen. Een tweede update in
dezelfde container is snel, want dan staat de venv er al — net als op een echte Pi.

## Waarom dit realistisch genoeg is

De container draait een 32-bit ARM-userland met **dezelfde Python als de doel-Pi**.
Dat is geen detail: `pip install` haalt op ARM andere wheels dan op arm64 of x86, en
pakketten zonder wheel worden vanaf broncode gebouwd. Juist dát is wat een deploy op
een Pi laat stranden.

Het basis-image volgt daarom de locatie:

| locatie | image | Python |
|---|---|---|
| west, noord | `arm32v7/debian:buster` | 3.7 |
| zuid | `balenalib/rpi-raspbian:bullseye` | 3.9 |
| wierden | `arm32v7/debian:bookworm` | 3.11 |

Overschrijven kan met `TESTPI_BASE=...`.

Voor zuid wordt bewust een Raspbian-image gebruikt: Debian bullseye is op dit moment
midden in de archivering (de live-mirror geeft 404 op de pakketten, en
`archive.debian.org` heeft nog geen `bullseye-security`), en Raspbian is voor deze
Pi's sowieso getrouwer. Let op dat dat image zich als `armv6l` meldt terwijl zuid
`armv7l` is; piwheels bedient die twee apart, dus een pakket kan daar in theorie een
andere wheel krijgen.

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
- **`--full` sloopte wierden.** De unit in de checkout wijst naar
  `/home/pi/AudioController`, maar wierden draait in `/home/gergemwierden/...`. Na
  `--full` startte de service niet meer: `cd: /home/pi/AudioController: No such file
  or directory`. Het script waarschuwde er alleen in tekst voor, en met `--yes`
  vervalt de bevestiging. `--full` zet die paden nu om naar de home van de
  doelgebruiker.
- **`run_audio_controller.sh` stond op 777** (wereld-schrijfbaar) op alle drie de
  Pi's, gezet door `update_pi.sh` zelf. Dat script draait via de unit als **root**,
  dus elke lokale gebruiker kon het herschrijven en bij de volgende herstart root
  worden. Nu 755. Let op: dat helpt pas bij een volgende `--full`; op de Pi's zelf
  staat het nog op 777 tot je het rechtzet.
- De healthcheck toonde `-> 000000` (curl schrijft zelf al `000`, en er stond nog een
  `|| echo 000` achter), en `--status` toonde `python:   line` als de venv ontbrak.
  Allebei gefixt in `update_pi.sh`.

## Getest per locatie

Elke locatie heeft een ander vertrekpunt, en dus een ander upgradepad:

| | versie op de Pi | Python | config | migratie | app-gebruiker |
|---|---|---|---|---|---|
| west | 1.5.0 | 3.7 | JSON v11 | geen | `pi` |
| noord | 1.0 | 3.7 | pickle **v8** | v8 → 9 → 10 → 11 | `pi` |
| zuid | 1.3 | **3.9** | pickle **v9** | v9 → 10 → 11 | `pi` |
| wierden | 1.3 | **3.11** | pickle **v9** | v9 → 10 → 11 | **`gergemwierden`** |

Met alleen west zou de **pickle → JSON-migratie** helemaal niet getest zijn; die was
op west al gebeurd. Juist daar zat eerder een bug (de v9-migratie die alle
instellingen resette, `1202acc`). Test daarom bij voorkeur tegen noord of wierden
voordat je die Pi's bijwerkt.

Uitkomst van die test: de migratie klopt op alle drie. noord ging van v8 naar v11 met
26 bronnen en 7 bestemmingen; zuid van v9 naar v11 met 20 bronnen en 6 bestemmingen;
wierden van v9 naar v11 met 10 bronnen en 4 bestemmingen. Namen steeds identiek aan de
pickle. Alle drie daarna service `active`, precies 1 instantie, `/` → 200 en
`/psalmbord` → 302.

### De testsuite draait op alle drie de Python-versies van het park

De 266 tests zijn niet alleen lokaal (3.9) gedraaid, maar ook op de andere twee
versies uit `docs/pi-specs.md`, elk in een schone container met een verse venv:

| Python | tornado | uitkomst |
|---|---|---|
| 3.7.17 (west, noord) | 6.2 | 266 passed |
| 3.9.6 lokaal (zuid) | 6.5.x | 266 passed |
| 3.11.16 (wierden) | 6.5.8 | 266 passed |

```bash
docker run --rm -v "$PWD/audio_controller:/src:ro" python:3.11-slim bash -c '
  printf "#!/bin/sh\nexit 0\n" > /usr/local/bin/sudo && chmod 755 /usr/local/bin/sudo
  cp -r /src /work && cd /work && rm -rf *.egg-info
  pip install -q -e . pytest && python -m pytest -q'
```

Die `sudo`-shim is nodig omdat de slim-images geen `sudo` hebben, terwijl
`soundcard.ensure_loopback_card()` als root `sudo modprobe snd-aloop` aanroept —
bij import al, via de module-level `Config()`. Op een Pi bestaat `sudo` wel; in een
kale container valt het collecten anders om met `FileNotFoundError: 'sudo'`.

### De dependency-versies lopen per Pi uiteen

`pip install --editable` upgradet niets dat al aan de eisen voldoet, dus een update
laat bestaande versies staan. Wat er nu draait tegenover wat een VERSE venv oplevert:

| | nu op de Pi | verse venv |
|---|---|---|
| west, noord (3.7) | tornado 6.1, python-socketio 5.3.0 | tornado 6.2, socketio 5.11.0 |
| zuid (3.9) | tornado 6.3.2, python-socketio 5.8.0 | tornado 6.5.8, socketio 5.16.4 |

Die verschillen blijven dus bestaan, en ze zijn niet academisch: Tornado 6.1 en 6.5
gedragen zich aantoonbaar anders (6.1 weigert een tweede `IOLoop(make_current=True)`
zolang de vorige nog 'current' is). Test bij twijfel tegen de Python van de doel-Pi.

### Terugrollen van een pickle-locatie is niet vanzelf veilig

De nieuwe versie migreert de pickle eenmalig naar json en **verwijdert hem daarna**
(unpicklen is onveilig, S2). Rol je vervolgens alleen de code terug, dan vindt de
oude versie geen pickle meer, kent json niet, en start met **fabrieksinstellingen**.
Dat is hier ook echt gebeurd: na een kale `--rollback` draaide wierden weer op 1.3,
maar met titel "Noorderkerk" in plaats van "GerGemWierden".

Met de config erbij gaat het wel goed:

```bash
./update_pi.sh wierden --rollback=<datum-tijd van vóór de update> --with-config --yes
```

Geverifieerd: dan staat de oorspronkelijke pickle terug (v9, GerGemWierden, 10
bronnen, 4 bestemmingen) en draait 1.3 weer met de eigen instellingen. Let op dat je
de backup van vóór de update aanwijst — elke rollback maakt zelf ook een backup, dus
"de nieuwste" wijst al snel naar de verkeerde staat.

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
