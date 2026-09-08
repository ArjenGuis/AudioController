# Nabootsing van west: Raspbian buster is Debian buster op armv7l, met Python 3.7.
FROM arm32v7/debian:buster

# buster is EOL, de repo's staan op archive.debian.org
# libxml2 + libxslt1.1: de piwheels-wheel van lxml linkt tegen de systeembibliotheken.
# Raspbian heeft die standaard staan; zonder deze twee installeert pip prima, maar valt
# de app om met 'libxslt.so.1: cannot open shared object file'.
# gcc/python3-dev staan ook op west, dus die horen er ook bij.
RUN printf 'deb http://archive.debian.org/debian buster main\ndeb http://archive.debian.org/debian-security buster/updates main\n' > /etc/apt/sources.list \
 && printf 'Acquire::Check-Valid-Until "false";\n' > /etc/apt/apt.conf.d/99no-check-valid \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
      openssh-server rsync sudo procps curl ca-certificates \
      python3 python3-venv python3-pip python3-dev \
      gcc libc6-dev \
      libxml2 libxslt1.1 \
 && rm -rf /var/lib/apt/lists/*

# Raspbian wijst pip naar piwheels: kant-en-klare armv7-wheels, zodat lxml (via
# onvif-zeep) niet vanaf broncode gebouwd hoeft te worden. Zonder dit faalt de
# pip-stap hier wel en op de Pi niet -- precies het soort verschil dat een
# testopstelling waardeloos maakt. west heeft exact deze /etc/pip.conf.
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

EXPOSE 22 5000 8080
CMD ["/usr/local/bin/entrypoint.sh"]
