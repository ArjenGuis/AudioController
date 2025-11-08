import logging
import os
import shutil
import sys
import time
import traceback
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from shell_process import global_shell, execute, in_shell, in_dir

module_name = 'index'
here = os.path.abspath(os.path.dirname(__file__))
path_to_python = os.path.join(here, 'transcrypt', 'python')
user_path = os.path.join(here, 'mbase_web', 'static', 'js')


def print_time(txt):
    print(f"{txt} (at {time.strftime('%H:%M:%S', time.localtime(time.time()))})")


def copy_to_webserver(path_to_python: str, module_name: str, user_path: str):
    """ Copy generated javascript to the webserver, the user of this lib """
    shutil.copy(os.path.join(path_to_python, '__target__', 'bundle', f"{module_name}.js"), user_path)


def bundle(path_to_python: str):
    """ Bundle javascript into one file, using webpack """
    print_time("Bundling")
    path = str(Path(path_to_python).parent)
    with in_dir(path):  # transcrypt folder, where folder node_modules is
        config_file = 'webpack.config.js'
        if not config_file in os.listdir(path):
            print(f"Warning: webpack config-file not found: {config_file}")
        cmd = f'npx webpack --config {config_file}'
        lines, return_code = execute(cmd, allow_error=True, silent=True, return_returncode=True)
        success = return_code == 0
        if success:
            print_time("Success")
            return True
        else:
            print_time("Failed")
            for line in lines:
                print(line)
    return False


def compile(path_to_python, module_name):
    """ Compile python code to javascript, using transcrypt """
    os.system('clear')  # clear screen
    print_time("Compiling")
    with in_dir(path_to_python):
        cmd = f'transcrypt --build --nomin --map {module_name}'
        # The transcrypt command does not write to stderr, so allow errors,
        # and check return_code. Then print lines if it failed.
        lines, return_code = execute(cmd, allow_error=True, silent=True, return_returncode=True)
        success = return_code == 0
        if success:
            print_time("Success")
        else:
            print_time("Failed")
            for line in lines:
                print(line)
    return success


class CompileEventHandler(FileSystemEventHandler):
    def __init__(self, path_to_python: str, module_name: str, user_path: str):
        self.timespan = 2.0  # minimum time needed between filesystem events, to trigger compilation
        self.last_time = time.time() - self.timespan * 2.0
        self.path_to_python = path_to_python
        self.module_name = module_name
        self.user_path = user_path

    def on_any_event(self, event):
        if time.time() > self.last_time + self.timespan:
            if compile(self.path_to_python, self.module_name):
                if bundle(self.path_to_python):
                    copy_to_webserver(self.path_to_python, self.module_name, self.user_path)
            self.last_time = time.time()


def main(path_to_python: str, module_name: str, user_path: str):
    """ 
    Watch directory `path_to_python` and compile python `module_name` on changes.
    Copy result to `user_path` (after bundling).
    """
    event_handler = CompileEventHandler(path_to_python, module_name, user_path)
    # fire directly:
    event_handler.on_any_event(None)
    observer = Observer()

    # observe 'path_to_python' non recursively, and all sub-directories recursively, excluding '__target__'
    observer.schedule(event_handler, path_to_python, recursive=False)
    for _, dirnames, _ in os.walk(path_to_python):
        for dirname in dirnames:
            if dirname != '__target__':
                observer.schedule(event_handler, str(Path(path_to_python) / dirname), recursive=True)
        break

    observer.start()
    try:
        while True:
            time.sleep(2)
        observer.stop()
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    args = sys.argv[1:]
    if args:
        path_to_python, module_name, user_path = (args[0], args[1], args[2])
        path_to_python = str(Path(path_to_python))
        user_path = str(Path(user_path))
    with in_shell():
        main(path_to_python, module_name, user_path)
