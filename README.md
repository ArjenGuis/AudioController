# Introduction

Control the routing of audio using a Raspberry Pi. This software runs on a Raspberry Pi and communicates with an ITEC audio controller (ITEC MultiMix) using the serial port. It provides a webinterface to easily connect an audio input source to multiple audio destinations.

Further, it can read audio from an url, and send it to a configurable input of the ITEC.
And the other way around: it is possible to send audio from an configurable ITEC output to an Icecast mountpoint.

The userinferface is created in the Dutch language. It consists of 2 pages; Control and Settings:

## Control screen
<img src="docs/pictures/screenshot_1.png" alt="drawing" width="700"/>
<p>

## Settings screen
<img src="docs/pictures/screenshot_2.png" alt="drawing" width="700"/>
<p>

# Howto deploy on raspberry pi

This is tested on Raspberry Pi version 3.
OS: Raspberry Pi OS version 2020-08-20.

## 1. Update OS and packages

### 1.1 Enable ssh
Option 1: Before inserting the sd card to the Pi, add a file named 'ssh' to the boot partition.
Option 2: Use Desktop environment to enable ssh

Add ssh key
```
PI_IP=192.168.1.96
ssh-copy-id -i ~/.ssh/id_ecdsa pi@${PI_IP}
```

Update
```
ssh pi@${PI_IP}
sudo apt update
sudo apt full-upgrade
```

Change default password
```
sudo raspi-config
```


## 2. Install Python and dependencies

### 2.1 Install python 3.7

Python 3.7+ is preinstalled on the OS. Also ffmpeg is preinstalled. Check this by running:
```
python3 --version
ffmpeg -version
```

### 2.2 Create a virtual environment

```
mkdir ~/AudioController
cd ~/AudioController
python3 -m venv pyenv
```

### 2.3 Install dependencies

```
source ./pyenv/bin/activate
python -m pip install --upgrade pip
python -m pip install pyserial
python -m pip install tornado
python -m pip install python-socketio
```

Optional:

```
sudo apt update
sudo apt install python3-gpiozero
python -m pip install gpiozero
python -m pip install rpi.gpio
```

## 3. Copy audio_controller project/package to pi

Check if ./audio_controller/audio_controller/static/js/main.js exists.
If not, first compile python code from ./transcrypt/python to generate main.js

Copy from local to pi (use correct ip-address):

```
scp -r ./audio_controller pi@${PI_IP}:~/AudioController
scp ./run_audio_controller.sh pi@${PI_IP}:~/AudioController
scp ./audio_controller.service pi@${PI_IP}:~/AudioController
scp ./audio_controller.html pi@${PI_IP}:~/Desktop
```

To install an update of the software it is usually enough to run the first command from above.


## 4. Create auto startup

Copy on pi, from home dir to /etc/systemd/system/

```
ssh pi@${PI_IP}
cd /home/pi/
sudo cp ./AudioController/audio_controller.service /etc/systemd/system/audio_controller.service
sudo chmod 777 ./AudioController/run_audio_controller.sh
sudo systemctl enable audio_controller.service
```

Some commands to start and stop service:

```
sudo systemctl status audio_controller.service
sudo systemctl start audio_controller.service
sudo systemctl stop audio_controller.service
sudo systemctl restart audio_controller.service
sudo systemctl enable audio_controller.service
sudo systemctl disable audio_controller.service
```

For a automatic daily restart of the service (at 4 o'clock):

```
sudo crontab -e
0 4 * * * systemctl restart audio_controller.service
```

To start the browser in kiosk mode, add the following lines to `/etc/xdg/lxsession/LXDE-pi/autostart`:
```
@xset s off
@xset -dpms
@xset s noblank
@chromium-browser --kiosk http://localhost:5000/
```
If it does not work, the last line should (maybe) be:
```
@chromium --kiosk http://localhost:5000/
```

For example the full file content becomes:
```
@lxpanel --profile LXDE-pi
@pcmanfm --desktop --profile LXDE-pi
@xscreensaver -no-splash
@xset s off
@xset -dpms
@xset s noblank
@chromium-browser --kiosk http://localhost:5000/
```

## 5. Use external USB sound card

Change number of default card from 0 to 1 in alsa.conf:
```
sudo nano /usr/share/alsa/alsa.conf
```
Change lines to match:
```
defaults.ctl.card 1
defaults.pcm.card 1
```
And play test sound (connect headphone to external device):
```
speaker-test -c2
```

## 6. Enable remote login

```
ssh pi@${PI_IP}
cd ~/AudioController/audio_controller/audio_controller/
sudo -s
python3
import utils
utils.add_user("<username>", "<password>")
assert utils.check_user("<username>", "<password>"), "Configuration failed"
exit()
```

## Extras

Disable updates

Enable NTP to have time updated
```
timedatectl status
sudo timedatectl set-ntp True
```

## Remarks

Make sure to place user file and settings file in home of root, not in home or pi user. AudioController runs as root user.

# How to contribute

User Linux as host. Windows is also possible, but not covered by this manual.

To read or write audio from/to an url, install ffmpeg.

...



