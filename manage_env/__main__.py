import os
import sys
import time
from pathlib import Path
from contextlib import contextmanager
import socket

from .shell_process import global_shell, execute, in_dir

here = Path(os.path.dirname(os.path.abspath(__file__)))
main_dir = here.parent

# make this script usable for diferent hosts:
hostname = socket.gethostname()
is_deploy = hostname.startswith("raspberrypi")

transcrypt_source = main_dir / "transcrypt"
transcrypt_dest = main_dir / "audio_controller" / "audio_controller" / "static" / "js"


@contextmanager
def active_env():
    with in_dir(main_dir):
        execute("source ./pyenv/bin/activate")
        yield
        execute("deactivate")


def create_env():
    """ Create/update virtual environment """
    # create environment if not exist
    if not (main_dir / "pyenv").exists():
        with in_dir(main_dir):
            # install venv on ubuntu by:
            # $ sudo apt-get install python3-venv
            execute("python3 -m venv pyenv")
        with active_env():
            execute("python -m pip install --upgrade pip")

    # install packages if not installed yet
    with active_env():
        installed = execute("pip list")[2:]

        def is_installed(name):
            for p in installed:
                if p.split()[0].lower() == name.lower():
                    print(f"Package {name} already installed")
                    return True
            return False

        def pip_install(name, args=""):
            if not is_installed(name):
                execute(f"python -m pip install {args} {name}")

        if not is_deploy:
            pip_install("pylint")
            pip_install("black")
            # pip_install("sphinx")

        pip_install("pyserial")
        pip_install("tornado")
        pip_install("python-socketio")

        # pip_install("urllib3")
        # pip_install("python-vlc")
        # pip_install("sounddevice")
        # pip_install("ffmpeg-python")  # also required: apt install ffmpeg
        # pip_install("pydub")  # also required: apt-get install ffmpeg libavcodec-extra
        # pip_install("simpleaudio")  # worked after apt-get install libasound2-dev
        # pip_install("pygame")
        # pip_install("numpy")

        if not is_deploy:
            pip_install("transcrypt")
            pip_install("watchdog")

        # install the app under development itself, so one app can be used by the other during development
        with in_dir(main_dir / 'audio_controller'):
            pip_install(".", "--editable")


def uninstall_nodejs():
    execute('yes | sudo apt-get purge nodejs')
    execute('yes | sudo apt-get autoremove')


def install_webpack():
    """ Install webpack, if not installed yet, which is needed for bundling javascript files """
    assert not is_deploy
    with in_dir(transcrypt_source):
        lines, return_code = execute(f'node -v', silent=True, allow_error=True, return_returncode=True)
        is_installed = return_code == 0
        if not is_installed:
            print("Nodejs not installed. Trying to install now.")
            execute('yes | sudo apt install nodejs', silent=False)
            execute('yes | sudo apt install npm', silent=False)
            execute('sudo npm install -g npx', silent=False)

        lines, return_code = execute(f'npx webpack --version', silent=True, allow_error=True, return_returncode=True)
        is_installed = return_code == 0
        if not is_installed:
            print("Webpack not installed. Trying to install now.")
            execute('npm init -y', silent=False)
            execute('npm install webpack webpack-cli --save-dev', silent=False)


def run_compile_on_save():
    """ Compile python to javascript """
    assert not is_deploy
    # uninstall_nodejs()
    install_webpack()
    module_name = 'main'
    path_to_python = str(transcrypt_source / 'python')
    user_path = str(transcrypt_dest)
    with active_env():
        with in_dir(here):
            try:
                # argument -u to have unbuffered output
                execute(f'python -u compile_on_save.py "{path_to_python}" "{module_name}" "{user_path}"',
                        allow_error=True, silent=False)
            except KeyboardInterrupt:
                pass


def generate_docs():
    """ Generate documentation """
    with active_env():
        if (main_dir / "docs" / "sphinx" / 'Makefile').exists():
            with in_dir(main_dir / "docs" / "sphinx"):
                execute("make html")
        else:
            print("Cannot generate documentation. First initialize sphinx by running 'sphinx-quickstart' from /docs/sphinx")


help_lines = [
    "Possible arguments:",
    " - (nothing): print this help",
    " - create_archive: create archive file of this project template",
    " - create_env: create/update virtual environement",
    " - compile_on_save: auto compile python to javascript on file changes",
    " - generate_docs: generate documentation using sphinx",
]


def print_help():
    print()
    for line in help_lines:
        print(line)
    print()


def main(args):
    if len(args) == 0 or args[0] == '--help':
        print_help()
        sys.exit(0)
    if args[0] == 'create_archive':
        create_archive()
    if args[0] == 'create_env':
        create_env()
    if args[0] == 'to_rasp':
        to_rasp()
    if args[0] == 'from_rasp':
        copy_readings_from_rasp()
    if args[0] == 'compile_on_save':
        run_compile_on_save()
    if args[0] == 'generate_docs':
        generate_docs()


if __name__ == '__main__':
    args = sys.argv[1:]  # first argument is path to this file, so skip this
    main(args)
