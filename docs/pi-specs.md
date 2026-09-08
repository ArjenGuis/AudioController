# Specificaties van de Pi's

Opgehaald op **2026-09-08/09** met een read-only script over ssh. Momentopname: versies,
uptime en temperatuur lopen uiteraard door.

## In één oogopslag

| | west | noord | zuid | wierden |
|---|---|---|---|---|
| **model** | Pi 3 Model B | Pi 3 Model B | Pi 3 Model B | **Pi 5 Model B** |
| **OS** | Raspbian 10 (buster) | Raspbian 10 (buster) | **Raspbian 11 (bullseye)** | **Raspbian 12 (bookworm)** |
| **kernel** | 5.10.17-v7+ | 5.4.51-v7+ | 6.1.21-v7+ | 6.12.47+rpt-rpi-v8 |
| **`uname -m`** | armv7l | armv7l | armv7l | aarch64 (64-bit kernel) |
| **userland** | armv7l | armv7l | armv7l | **armv8l — 32-bit** |
| **Python** | **3.7.3** | **3.7.3** | **3.9.2** | **3.11.2** |
| **RAM** | 924 MB | 925 MB | 921 MB | 16 GB |
| **schijf** | 29 GB (12% vol) | 15 GB (24% vol) | 29 GB (**48% vol**) | 230 GB (5% vol) |
| **app-versie** | 1.5.0 | **1.0** | **1.3** | **1.3** |
| **config** | json v11 | **pickle v8** | **pickle v9** | **pickle v9** |
| **ssh-user** | `pi` | `pi` | `pi` | **`gergemwierden`** |
| **app-map** | `/home/pi/AudioController` | idem | idem | `/home/gergemwierden/AudioController` |
| **service-user** | root | root | root | root |
| **ITEC (serieel)** | pl2303 → `ttyUSB0` | **FTDI FT232** → `ttyUSB0` | **FTDI FT232** → `ttyUSB0` | **geen** |
| **USB-audio** | PCM2902 | PCM2902 | PCM2902 | **geen** |
| **ffmpeg** | 4.1.6 | 4.1.6 | 4.3.8 | 5.1.7 |
| **uptime** | 5 dagen | **17 weken** | **21 weken** | **35 weken** |

Alle vier: 4 cores, service draait als **root** (config dus in `/root/`), en
`/etc/pip.conf` wijst naar piwheels.

**Vier Pi's, vier OS/Python-combinaties.** De code moet dus werken op Python 3.7, 3.9
én 3.11. Dat is geen theorie: de `asyncio.Lock()`-valkuil die we in `controller.py`
tegenkwamen speelt op 3.7 én 3.9 (de loop-binding verdween pas in 3.10).

## Waarom die verschillen ertoe doen

**west en noord zijn Pi 3's met Python 3.7.** Daar geldt alles wat we deze week
tegenkwamen: de `SameSite`-cookiecompat (#16), de trage ONVIF-handshake, en de
`asyncio.Lock()`-valkuil op 3.7. De testopstelling in `testpi/` bootst precies deze
machines na.

**wierden is een heel andere machine.** Pi 5, bookworm, Python 3.11, 16 GB RAM. De
3.7-specifieke problemen spelen daar niet. Let op: `uname -m` zegt `aarch64` (dat is de
kernel), maar de userland is 32-bit — Python meldt platformtags `armv8l`, en piwheels
levert er `linux_armv7l`-wheels voor.

**wierden heeft geen ITEC en geen USB-geluidskaart.** Er is geen `/dev/ttyUSB*` en de
enige geluidskaarten zijn Loopback en HDMI. De seriële fixes van deze week zijn daar
dus niet van toepassing.

**noord en zuid gebruiken een andere seriële adapter** dan west: een FTDI FT232 in
plaats van een pl2303. De bus-contentie-analyse (bulk-transfers die het aflegden tegen
isochrone USB-audio) is op west gemeten; op noord en zuid kan dat anders liggen.

**noord, zuid en wierden staan nog op de legacy pickle**, alleen west al op json v11.
Een update van die drie draait dus de pickle→json-migratie; die van west niet.

**zuid draait Python 3.9.** Dat is de derde Python-versie in het park. Ook op 3.9 bindt
`asyncio.Lock()` zich bij het aanmaken aan de event loop (dat verdween pas in 3.10), dus
de valkuil die we in `controller.py` oplosten speelde daar net zo goed.

## Per locatie

### west — `west.gergemrijssen.nl:2222` (user `pi`)

```
model          Raspberry Pi 3 Model B Rev 1.2   serial 00000000217445e0
os             Raspbian GNU/Linux 10 (buster)   kernel 5.10.17-v7+   armv7l
cpu            ARMv7 Processor rev 4 (v7l), 4 cores
ram            924 MB          schijf 29G totaal, 3.4G gebruikt (12%)
python         3.7.3 (systeem en venv)
app            1.5.0           config json v11, titel "GG Rijssen-West"
service        root, active     logging aan
usb            pl2303 seriële adapter (ATEN UC-232A); PCM2902 Audio Codec
serieel        /dev/ttyUSB0
geluidskaarten bcm2835 Headphones; Loopback; USB Audio CODEC
ffmpeg         4.1.6            ip 192.168.1.42
```

Camera's: Kerk `192.168.1.9`, Zaal `192.168.1.10` (ONVIF poort 2000).

### noord — `noord.gergemrijssen.nl:2222` (user `pi`)

```
model          Raspberry Pi 3 Model B Rev 1.2   serial 000000003fe4b6e5
os             Raspbian GNU/Linux 10 (buster)   kernel 5.4.51-v7+   armv7l
cpu            ARMv7 Processor rev 4 (v7l), 4 cores
ram            925 MB          schijf 15G totaal, 3.3G gebruikt (24%)
python         3.7.3 (systeem en venv)
app            1.0             config legacy pickle (v8), titel "GG Rijssen-Noord"
service        root, active     uptime 17+ weken
usb            FTDI FT232 seriële adapter; PCM2902 Audio Codec
serieel        /dev/ttyUSB0
geluidskaarten bcm2835 Headphones; Loopback; USB Audio CODEC
ffmpeg         4.1.6            ip 192.168.178.21
```

Config: 26 bronnen, 7 bestemmingen.

### wierden — `194.122.241.158:2222` (user `gergemwierden`)

```
model          Raspberry Pi 5 Model B Rev 1.1   serial c9a38c9dd900322e
os             Raspbian GNU/Linux 12 (bookworm) kernel 6.12.47+rpt-rpi-v8
uname -m       aarch64 (kernel)   userland armv8l (32-bit)
cores          4
ram            16003 MB        schijf 230G totaal, 8,9G gebruikt (5%)
python         3.11.2 (systeem en venv)
app            1.3             config legacy pickle (v9), titel "GerGemWierden"
service        root, active     uptime 35+ weken
usb            SiGma Micro toetsenbord; Logitech Nano Receiver
serieel        GEEN /dev/ttyUSB*
geluidskaarten Loopback; vc4-hdmi-0; vc4-hdmi-1
ffmpeg         5.1.7            ip 192.168.2.51
```

Config: 10 bronnen, 4 bestemmingen. `lxml` staat hier nog niet geïnstalleerd — versie
1.3 is van vóór de camera/ONVIF-functie.

### zuid — `zuid.gergemrijssen.nl:2222` (user `pi`)

```
model          Raspberry Pi 3 Model B Rev 1.2   serial 000000003fdfa5d7
os             Raspbian GNU/Linux 11 (bullseye) kernel 6.1.21-v7+   armv7l
cpu            ARMv7 Processor rev 4 (v7l), 4 cores
ram            921 MB          schijf 29G totaal, 14G gebruikt (48%)
python         3.9.2 (systeem en venv)
app            1.3             config legacy pickle (v9), titel "GG Rijssen-Zuid"
service        root, active     uptime 21 weken
usb            FTDI FT232 seriële adapter; PCM2902 Audio Codec
serieel        /dev/ttyUSB0
geluidskaarten bcm2835 Headphones; Loopback; USB Audio CODEC; vc4-hdmi
ffmpeg         4.3.8            ip 192.168.1.8
```

Config: 20 bronnen, 6 bestemmingen. Hostkeys, bevestigd op 2026-09-09:

```
ED25519  SHA256:MGw/RcQC8FFJISBKnWD6hNjQFk1fWvwAKX3EQgV4pxI
ECDSA    SHA256:1qCbJ+e1p4nyxl/44EQAsaPqMCf3KV37JKvhPUjBGpI
RSA      SHA256:NFmP11aISsGurLa1neUySRTmDQoms9INbckCVGOYzkg
```

Bij het inloggen toont zuid nog de standaard Raspberry Pi-banner ("SSH may not work
until a valid user has been set up"); onschuldig, maar het duidt op een niet
afgeronde eerste-installatie.

## Bekende aandachtspunten

- **`run_audio_controller.sh` staat op alle vier op 777** (wereld-schrijfbaar) terwijl
  de service dat script als root uitvoert. `update_pi.sh` zet dat sinds
  `5443022`/`e14952e` op 755, maar dat werkt pas bij een volgende `--full`; op de Pi's
  zelf staat het nog op `-rwxrwxrwx`.
- **`testpi/` kiest zijn basis-image per locatie** (buster/bullseye/bookworm), zodat de
  venv- en pip-stap op de juiste Python getest wordt. Wat het niet nabootst is de
  hardware: geen ITEC, geen geluidskaart, geen camera's, en geen echte systemd.
- **noord 17 weken, zuid 21 weken en wierden 35 weken** zonder herstart. Geen probleem
  op zichzelf, maar kernel- en securityupdates zijn daar dus al lang niet toegepast.
- **zuid's schijf is voor 48% vol** (14 van 29 GB) — de volste van de vier. noord heeft
  met 15 GB de kleinste schijf.
- **zuid toont bij het inloggen nog de standaard Raspberry Pi-banner** over een niet
  ingestelde gebruiker.

## Hoe dit opnieuw op te halen

Het verzamelscript staat niet in de repo (het is een wegwerpding); alles komt uit
read-only commando's: `/proc/device-tree/model`, `/etc/os-release`, `uname`, `free`,
`df`, `lsusb`, `aplay -l`, `vcgencmd measure_temp`, plus `systemctl show` en de
app-config via `sudo`. Zie ook `./update_pi.sh <locatie> --status` voor een snelle
samenvatting per Pi.
