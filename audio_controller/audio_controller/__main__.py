# python standard lib
import os
import sys
import time
from pathlib import Path
import traceback
import argparse
import asyncio
import logging

# externals
import tornado.ioloop
import tornado.web
import socketio

# internals
from . import loggers  # load logging first, before other modules
from . import settings
from .handlers import handlers
from . import stream
from . import itec
from . import controller
from . import user
from . import gpio

here = Path(os.path.dirname(__file__)).resolve()
main_logger = logging.getLogger("main")


def make_app():
    template_dir = here / "views"
    static_dir = here / "static"
    settings = dict(
        debug=False,
        autoreload=False,
        cookie_secret=user.get_cookie_secret(),
        template_path=str(template_dir),
    )

    sio = socketio.AsyncServer(async_mode="tornado")
    handlers.websocket_handlers(sio)

    _handlers = [
        ("/", handlers.Main),
        ("/login/.*", handlers.Login),
        ("/general/.*", handlers.General),
        ("/psalmbord", handlers.Psalmbord),
        ("/camera", handlers.CameraApp),
        ("/camera/.*", handlers.Camera),
        ("/(favicon.ico)", handlers.StaticFileHandler, {"path": str(static_dir)}),
        ("/static/(.*)", handlers.StaticFileHandler, {"path": str(static_dir)}),
        ("/websocket/", socketio.get_tornado_handler(sio)),
    ]

    return tornado.web.Application(handlers=_handlers, **settings)


def schedule_tasks(loop: asyncio.BaseEventLoop):
    """Add additional async tasks to the same event-loop as the running webserver."""
    loop.create_task(controller.scan_ports())
    loop.create_task(controller.auto_switch())
    loop.create_task(set_gpio())


def init_system(args):
    """initialize system"""
    import getpass

    volume = "100%"
    try:
        if "--volume" in args:
            v = args[args.index("--volume") + 1]
            if "%" in v:
                volume = v
    except:
        pass
    # set the output volume level to a fixed percentage
    # TODO use module soundcard here, to identify the device
    # cmd = f"amixer -M sset 'Master' {volume}" # without external sound card
    cmd = f"amixer -M sset 'PCM' {volume}"  # with external sound card
    print(cmd)
    msg = os.popen(cmd).read()
    print(msg)
    main_logger.info(msg)

    # log user
    msg = f"Init system - user: {getpass.getuser()}"
    print(msg)
    main_logger.info(msg)


async def set_gpio():
    # activate leds on warnings / errors
    if gpio.is_enabled:
        gpio.power_button.handle_reboot = lambda: os.system("shutdown -r now")
        interval_seconds = 4
        while True:
            try:
                connected = False
                # if there is at least 1 destination selected, connected becomes True
                if settings.settings.connect_source_destination:
                    for dest in settings.destinations:
                        if dest.enabled and dest.selected:
                            connected = True
                            break
                gpio.source_and_destination_connected(connected)
            except:
                pass
            await asyncio.sleep(interval_seconds)


def main():
    args = sys.argv[1:]
    try:
        init_system(args)
        # listen on 2 ports, 5000 for localhost and 8080 for external usage (external usage requires login)
        port_address = [(5000, "127.0.0.1"), (8080, "0.0.0.0")]
        for port, address in port_address:
            app = make_app()
            app.listen(port=port, address=address)
            msg = f"Listening on {address}:{port}"
            print(msg)
            main_logger.info(msg)

        ioloop = tornado.ioloop.IOLoop.current()
        schedule_tasks(ioloop.asyncio_loop)
        controller.set_routes()
        if not settings.settings.enable_logging:
            main_logger.info("Logging is disabled")
            loggers.enable(False)
        ioloop.start()
    except Exception:
        msg = f"Application stopped with exception: \n{traceback.format_exc()}"
        print(msg)
        main_logger.error(msg)
    except KeyboardInterrupt:
        msg = "Application stopped"
        print(msg)
        main_logger.info(msg)


if __name__ == "__main__":
    stream.test()
    itec.test()
    settings.test()
    user.test()
    main()
