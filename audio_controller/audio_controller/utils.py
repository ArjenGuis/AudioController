""" """

import random
import string
import hashlib
import os, sys
from pathlib import Path


# file to save usernames and passwords
file_users = Path.home() / ".audio_controller_users.txt"
# file to save cookie secret
file_cookie = Path.home() / ".audio_controller_cookie.txt"

for file in [file_users, file_cookie]:
    if not file.exists():
        with open(file, 'w'):
            pass


def clear_users():
    with open(file_users, 'w') as f:
        f.writelines([])


def add_user(username: str, password: str):
    assert ";" not in username
    pw = hashlib.blake2b(password.encode()).hexdigest()
    line = f"{username};{pw}\n"
    with open(file_users, 'a') as f:
        f.write(line)


def check_user(username: str, password: str):
    pw = hashlib.blake2b(password.encode()).hexdigest()
    with open(file_users, 'r') as f:
        lines = f.readlines()
    for line in lines:
        [username_, pw_] = line.split(";")
        pw_ = pw_.strip()  # remove "\n"
        if username == username_ and pw == pw_:
            return True
    return False


def get_cookie_secret():
    with open(file_cookie, 'r') as f:
        lines = f.readlines()
    if lines:
        return lines[0].strip()  # remove "\n"
    else:
        random_string = ''.join(random.choice(string.ascii_letters) for i in range(30))
        secret = hashlib.sha256(random_string.encode()).hexdigest()
        with open(file_cookie, 'a') as f:
            line = f"{secret}\n"
            f.write(line)
            return secret


def test():

    return

    sys.exit(0)
