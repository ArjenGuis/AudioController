#!/bin/bash
set -e
ssh-keygen -A >/dev/null 2>&1 || true
touch /var/log/audio_controller.log
/usr/sbin/sshd -D -e
