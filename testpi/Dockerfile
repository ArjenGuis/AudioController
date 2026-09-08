# Nabootsing van een kerk-Pi. De vier locaties draaien vier verschillende
# OS/Python-combinaties, dus het basis-image is instelbaar; start.sh kiest hem per
# locatie. Alle Pi's draaien een 32-bit ARM-userland (ook wierden, dat een 64-bit
# kernel heeft maar armv8l-userland), vandaar arm32v7.
#
#   buster   -> Python 3.7   (west, noord)
#   bullseye -> Python 3.9   (zuid)
#   bookworm -> Python 3.11  (wierden)
ARG BASE=arm32v7/debian:buster
FROM ${BASE}

# buster en bullseye zijn EOL en verhuisd naar archive.debian.org; bookworm niet.
# libxml2 + libxslt1.1: de piwheels-wheel van lxml linkt tegen de systeembibliotheken.
# Raspbian heeft die standaard staan; zonder deze twee installeert pip prima, maar valt
# de app om met 'libxslt.so.1: cannot open shared object file'.
# gcc/python3-dev staan ook op de Pi's, dus die horen er ook bij.
# Alleen buster is zo oud dat zijn repo's naar archive.debian.org verhuisd zijn;
# bullseye en bookworm worden nog van deb.debian.org geserveerd, dus die laten we met
# rust (een archive-only repo mist er pakketten -> 'held broken packages'). De
# vervaldatumcontrole gaat wel voor alle drie uit: bullseye's security-Release is
# inmiddels verlopen, en dat blokkeert anders de hele apt-update.
RUN set -e; \
    . /etc/os-release; \
    case "$VERSION_CODENAME" in \
      buster) \
        printf 'deb http://archive.debian.org/debian buster main\ndeb http://archive.debian.org/debian-security buster/updates main\n' > /etc/apt/sources.list ;; \
    esac; \
    printf 'Acquire::Check-Valid-Until "false";\n' > /etc/apt/apt.conf.d/99no-check-valid; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      openssh-server rsync sudo procps curl ca-certificates \
      python3 python3-venv python3-pip python3-dev \
      gcc libc6-dev \
      libxml2 libxslt1.1; \
    rm -rf /var/lib/apt/lists/*

# Raspbian wijst pip naar piwheels: kant-en-klare ARM-wheels, zodat lxml (via
# onvif-zeep) niet vanaf broncode gebouwd hoeft te worden. Zonder dit faalt de
# pip-stap hier wel en op de Pi niet -- precies het soort verschil dat een
# testopstelling waardeloos maakt. Alle vier de Pi's hebben deze /etc/pip.conf.
RUN printf '[global]\nextra-index-url=https://www.piwheels.org/simple\n' > /etc/pip.conf

# gebruiker pi, zoals op de Pi, met sudo zonder wachtwoord
RUN useradd -m -s /bin/bash pi \
 && echo 'pi ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/pi \
 && mkdir -p /var/run/sshd /home/pi/.ssh \
 && chown -R pi:pi /home/pi/.ssh && chmod 700 /home/pi/.ssh

# authorized_keys wordt bij het starten gevuld door start.sh (jouw publieke sleutel;
# bewust niet in het image gebakken)

COPY systemctl /usr/local/bin/systemctl
COPY journalctl /usr/local/bin/journalctl
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/systemctl /usr/local/bin/journalctl /usr/local/bin/entrypoint.sh

# balenalib-images zetten een eigen ENTRYPOINT; die moet weg, anders wordt onze CMD
# als argument daaraan doorgegeven in plaats van uitgevoerd.
ENTRYPOINT []

EXPOSE 22 5000 8080
CMD ["/usr/local/bin/entrypoint.sh"]
