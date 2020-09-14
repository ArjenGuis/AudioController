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
# internals
from . import loggers
from . import settings
from .handlers import handlers
from . import stream
from . import itec
from . import controller
from . import utils

here = Path(os.path.dirname(__file__)).resolve()
main_logger = logging.getLogger("main")


def make_app():
    template_dir = here / 'views'
    static_dir = here / 'static'
    settings = dict(
        debug=False,
        autoreload=False,
        cookie_secret=utils.get_cookie_secret(),
        template_path=str(template_dir),
    )
    _handlers = [
        ("/", handlers.Main),
        ("/login/.*", handlers.Login),
        ("/websocket", handlers.WebSocket),
        ("/general/.*", handlers.General),
        ("/(favicon.ico)", tornado.web.StaticFileHandler, {'path': str(static_dir)}),
        ("/static/(.*)", tornado.web.StaticFileHandler, {'path': str(static_dir)}),
    ]
    return tornado.web.Application(handlers=_handlers, **settings)


def schedule_tasks(loop: asyncio.BaseEventLoop):
    """ Add additional async tasks to the same event-loop as the running webserver. """
    loop.create_task(controller.scan_ports())
    loop.create_task(controller.auto_switch())


def init_system():
    """ initialize system  """
    import getpass
    # set the output volume level to a fixed percentage
    os.system("amixer sset 'Master' 80%")
    # log user
    msg = f"Init system - user: {getpass.getuser()}"
    print(msg)
    main_logger.info(msg)


def main():
    try:
        init_system()
        # listen on 2 ports, 5000 for localhost and 8080 for external usage (external usage requires login)
        port_address = [(5000, '127.0.0.1'), (8080, '0.0.0.0')]
        for (port, address) in port_address:
            app = make_app()
            app.listen(port=port, address=address)
            print(f"Listening on {address}:{port}...")

        ioloop = tornado.ioloop.IOLoop.current()
        schedule_tasks(ioloop.asyncio_loop)
        controller.set_routes()
        ioloop.start()
    except Exception:
        msg = f"Application stopped with exception: \n{traceback.format_exc()}"
        print(msg)
        main_logger.error(msg)
    except KeyboardInterrupt:
        msg = "Application stopped"
        print(msg)
        main_logger.info(msg)


if __name__ == '__main__':
    # stream.test()
    itec.test()
    # settings.test()
    utils.test()
    main()
