# python standard lib
import os
import sys
import signal
import logging
import math
import datetime as dt
import time
import json
from json import dumps
from pathlib import Path
import traceback
from dataclasses import asdict
import asyncio

# external libs
import socketio
import tornado
import tornado.web

# import tornado.websocket

# internals
from audio_controller import settings, controller, utils, loggers, gpio, __version__

here = Path(os.path.dirname(__file__)).resolve()
main_logger = logging.getLogger("main")


class BaseHandler(tornado.web.RequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def body_to_json(self):
        body = self.request.body
        if not body:
            body = b"{}"
        return json.loads(body)

    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS, HEAD, PUT")
        self.set_header(
            "Access-Control-Allow-Headers",
            "Origin, X-Requested-With, Content-Type: application/json, Accept, Authorization",
        )

    def get_current_user(self):
        """Overrides method, gets called ones when accessing 'self.current_user'"""
        r = self.get_secure_cookie("audio_controller_user")
        if r is not None:
            return r.decode("utf-8")
        return r

    def set_cookie_username(self, username: str = ""):
        self.set_secure_cookie("audio_controller_user", username.encode("utf-8"))

    def logged_in(self):
        """Return True if user is logged in, False otherwise."""
        return bool(self.current_user)

    def login_required(self):
        """Check if login is required, which is always except when request comes from localhost"""
        return not self.is_localhost()

    def is_localhost(self):
        """Return True if request comes from localhost (when port is 5000 this is True). False otherwise"""
        return self.request.host.endswith(":5000")

    def write_login_exception(self):
        self.write(dumps({"LoginException": "Please login first"}))


def get_action(path: str):
    """get action from path, where path is assumed to be '/{controller}/{action}.*'"""
    items = path.lstrip("/").split("/")
    if len(items) > 1:
        return items[1]
    return None


def get_js_filename():
    """Rename main.js to an unique file name, to force reload. Return latest file renamed from main.js."""
    js_dir = here.parent / "static" / "js"
    names = os.listdir(str(js_dir))
    names = [n for n in names if n.startswith("main") and n.endswith(".js")]
    if "main.js" in names:
        for n in names:
            if n != "main.js":
                os.remove(js_dir / n)
        new_name = f"main-{int(time.time())}.js"
        os.rename(js_dir / "main.js", js_dir / new_name)
        return new_name
    else:
        return sorted(names)[-1]


class StaticFileHandler(tornado.web.StaticFileHandler):
    def set_extra_headers(self, path):
        # Disable cache
        self.set_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")


class Main(BaseHandler):
    def get(self):
        self.render("index.html", title="Title", page="home", js_filename=get_js_filename(), version=__version__)

    def post(self):
        self.write("")


class Psalmbord(tornado.web.RequestHandler):
    def body_to_json(self):
        body = self.request.body
        if not body:
            body = b"{}"
        return json.loads(body)

    def get(self):
        if settings.settings.enable_psalmbord:
            fs = settings.psalmbord.fontsize
            fw = settings.psalmbord.fontweight
            css = f"html {{ --regels: {fs}; }} \n .font_weight {{ font-weight: {fw}; }}"
            self.render("psalmbord.html", css=css)
        else:
            html = """<!DOCTYPE html><html><body style="background-color: black;"></body></html>"""
            self.write(html)

    def post(self):
        if settings.settings.enable_psalmbord:
            kwargs = self.body_to_json()
            if kwargs.get("html"):
                self.write(settings.psalmbord_as_html())
            else:
                self.write(dumps(asdict(settings.psalmbord)))
        else:
            self.write(dumps(asdict(settings.Psalmbord())))


class Login(BaseHandler):
    def check_user(self, username, password):
        """Check if user has provided correct password to login"""
        if username is None or password is None:
            return False
        return utils.check_user(username, password)

    def post(self):
        action = get_action(self.request.path)

        if action == "login_required":
            self.write(dumps({"login_required": self.login_required()}))
            return

        if action == "login":
            # check if already logged in (reading cookie)
            if self.current_user:  # not None and not empty string
                return self.write(dumps({"success": True}))
            else:
                # try login if arguments are provided
                args = self.body_to_json()
                # self.get_arguments
                # if 'username' in args and 'password' in args:
                username = str(args.get("username"))
                password = str(args.get("password"))
                if self.check_user(username, password):
                    msg = f"Login user {username}"
                    print(msg)
                    main_logger.info(msg)
                    self.set_cookie_username(username)  # assumes unique usernames
                    self.write(dumps({"success": True}))
                else:
                    msg = f"Login failed for user {username}"
                    print(msg)
                    main_logger.info(msg)
                    self.write(dumps({"success": False}))

        elif action == "logout":
            # remove cookie user
            self.set_cookie_username("")
            self.write(dumps({"success": True}))
            # self.redirect_relative("/")  # not used, implemented client side

        # elif action == 'register': ??


class General(BaseHandler):
    async def post(self):
        action = get_action(self.request.path)

        if action == "connected":
            if controller.itec.serial is None:
                raise tornado.web.HTTPError(503)  # 503 = Dienst niet beschikbaar
            self.write(dumps({"success": True}))
            return

        if self.login_required() and not self.logged_in():
            self.write(dumps({"success": False}))
            return

        def write_settings():
            self.write(dumps(asdict(settings.settings)))

        def write_sources():
            self.write(dumps([asdict(obj) for obj in settings.sources]))

        def write_destinations():
            self.write(dumps([asdict(obj) for obj in settings.destinations]))

        if action == "restoreSettings":
            settings.restore()
            write_settings()
            return

        elif action == "getSettings":
            write_settings()
            return

        elif action == "setSettings":
            args = self.body_to_json()
            settings.update_settings(args)
            controller.set_routes()
            loggers.enable(settings.settings.enable_logging)
            write_settings()
            await notify_change()
            return

        elif action == "getSources":
            write_sources()
            return

        elif action == "setSources":
            args = self.body_to_json()
            sources = args["sources"]
            settings.update_sources(sources)
            controller.set_routes()
            write_sources()
            await notify_change()
            return

        elif action == "getDestinations":
            write_destinations()
            return

        elif action == "setDestinations":
            args = self.body_to_json()
            destinations = args["destinations"]
            settings.update_destinations(destinations)
            controller.set_routes()
            write_destinations()
            await notify_change()
            return

        elif action == "getPsalmbord":
            self.write(dumps(asdict(settings.psalmbord)))
            return

        elif action == "setPsalmbord":
            args = self.body_to_json()
            settings.update_psalmbord(
                args["title"], args["regels"], args["fontfamily"], args["fontsize"], args["fontweight"]
            )
            self.write(dumps(asdict(settings.psalmbord)))
            return

        elif action == "getInputLevels":
            levels = controller.config.current_levels
            self.write(dumps(levels))
            return

        elif action == "downloadLog":
            self.write(loggers.get_logs_as_binary())
            return

        elif action == "ifconfig":
            self.write(os.popen("ifconfig").read())
            return

        elif action == "soundcards":
            aplay = os.popen("aplay -l").read()
            arecord = os.popen("arecord -l").read()
            self.write(f"{aplay}\n{arecord}")
            return

        elif action == "reboot":
            os.system("shutdown -r now")
            return

        elif action == "shutdown":
            os.system("shutdown now")
            return

        elif action == "getRoutes":
            self.write(controller.get_routes())
            return

        elif action == "downloadSettings":
            self.write(settings.get_binary())
            return

        elif action == "uploadSettings":
            file_content = self.request.files["file"][0]["body"]
            settings.set_binary(file_content)
            self.write(dumps({"success": True}))
            return

        elif action == "test_gpio":
            if gpio.is_enabled:
                await gpio.test_async()
            return


async def notify_change():
    """Notify clients that there has been changed something, like a setting"""
    for server in websocket_servers:
        await server.emit("event", "change")


websocket_servers: socketio.Server = []


def websocket_handlers(sio: socketio.Server):
    if sio in websocket_servers:
        return

    # multiple (tornado) applications run on different ports, so for each a server exists
    websocket_servers.append(sio)

    @sio.event
    async def connect(sid, environ):
        handler = environ["tornado.handler"]
        handler = BaseHandler(handler.application, handler.request)
        if handler.login_required() and not handler.logged_in():
            print("Unauthorized websocket usage, websocket closed.")
            return False
        # print('connect ', sid)

    @sio.event
    def disconnect(sid):
        pass  # print('disconnect ', sid)

    @sio.event
    def event(sid, data):
        pass  # print("event catched")
        # print(data)

    # @sio.on('my custom event')
    # def another_event(sid, data):
    #     print("custom event catched")
