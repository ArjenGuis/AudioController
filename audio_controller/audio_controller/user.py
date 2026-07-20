""" """

import random
import string
import hashlib
import os, sys
from pathlib import Path
from dataclasses import dataclass, field, asdict, is_dataclass



# file to save usernames and passwords
file_users = Path.home() / ".audio_controller_users.txt"
# file to save cookie secret
file_cookie = Path.home() / ".audio_controller_cookie.txt"

for file in [file_users, file_cookie]:
    if not file.exists():
        with open(file, 'w'):
            pass

@dataclass
class User:
    username: str
    password: str
    admin: bool = False
    camera: bool = False


def clear_users():
    with open(file_users, 'w') as f:
        f.writelines([])


def add_user(username: str, password: str):
    assert ";" not in username
    pw = encryptPassword(password)
    line = f"{username};{pw}\n"
    with open(file_users, 'a') as f:
        f.write(line)


def check_user(username: str, password: str):
    pw = encryptPassword(password)
    with open(file_users, 'r') as f:
        lines = f.readlines()
    for line in lines:
        [username_, pw_] = line.split(";")
        pw_ = pw_.strip()  # remove "\n"
        if username == username_ and pw == pw_:
            return True
    return False


def get_users():
    users: list[User] = []

    with open(file_users, "r") as f:
        for line in f:
            username, password = line.strip().split(";")
            users.append(
                User(
                    username=username,
                    password=password
                )
            )

    return users

def encryptPassword(password):
    return hashlib.blake2b(password.encode()).hexdigest()

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


def default_users():
    """ Default users, used as initial and factory defaults """
    result = [
        User('admin', "admin", True, True),
    ]
    for i, obj in enumerate(result):
        obj.id = i
    return result


def test():
    return
    sys.exit(0)
