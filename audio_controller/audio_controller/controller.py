
""" purpose: route input to output """
# standard lib
from typing import List
import asyncio
import logging

# externals

# internals
from . import itec as itec_module
from .itec import itec
from . import settings
from .settings import Source, Destination
from . import stream


main_logger = logging.getLogger("main")


def get_IN_port(source: Source) -> int:
    """ Get ITEC IN port nr, also if it is an url. """
    result = settings.get_IN_port(source.port_url)
    if result is None:
        result = settings.get_IN_port(settings.settings.port_IN_for_streams)
    return result


class Config:
    """ Holds configuration, which consists of connections from input to output ports.
    """

    def __init__(self):
        self.current_levels = {}  # key = source-id, value = dict (keys: 'level', 'threshold', and 'prio')
        self.process_play = ()  # tuple (url, FfmpegProcess)
        self.process_send = ()  # tuple (urls, FfmpegProcess)

    def set_routes(self, sources: List[Source], destinations: List[Destination]):
        """ 
        Set routes on ITEC to route audio from selected sources to selected destinations.
        Sources and destinations must all be enabled.
        """

        def route_all_to_null():
            #print("route all to null")
            ports = [get_IN_port(s) for s in sources]
            for p in ports:
                itec.set_route(p, [])

        def stop_start_play(url: str):
            """ Stop and start playing url on analog output, if needed, based on the given url (which can be None) """
            # stop
            if self.process_play and self.process_play[0] != url:
                self.process_play[1].stop()
                self.process_play = ()

            # start
            if not self.process_play and url is not None:
                self.process_play = (url, stream.play_process(url))

        def stop_start_send(urls: List[str]):
            """ Stop and start process sending analog output to urls, if needed, based on the given urls """
            # stop
            urls = sorted(urls)
            if self.process_send and self.process_send[0] != urls:
                self.process_send[1].stop()
                self.process_send = ()

            # start
            if not self.process_send and len(urls) > 0:
                self.process_send = (urls, stream.send_process(urls))

        def stop_all():
            route_all_to_null()
            stop_start_play(None)
            stop_start_send([])

        if not settings.settings.connect_source_destination or not destinations:
            stop_all()
            return

        selected_source = None
        for source in sources:
            if source.selected:
                selected_source = source
                break

        if selected_source is None:  # nothing selected
            stop_all()
            return

        # determine which IN-port must be routed
        port_in: int = None
        url_in: str = None
        urls_out: List[str] = []

        port_in = settings.get_IN_port(selected_source.port_url)
        if port_in is None:
            # selected source is not a port, but an url
            port_in = settings.get_IN_port(settings.settings.port_IN_for_streams)
            url_in = selected_source.port_url

        # disable all IN ports which are not selected
        ports = [get_IN_port(s) for s in sources if not s.selected]
        for p in ports:
            if p != port_in:
                itec.set_route(p, [])

        # select all OUT ports which must get route, and select urls to which audio must be send
        ports_out = []
        for d in destinations:
            if d.selected:
                port_out = settings.get_OUT_port(d.port_url_file)
                if port_out is None:
                    port_out = settings.get_OUT_port(settings.settings.port_OUT_to_stream)
                    if port_out is not None:
                        urls_out.append(d.port_url_file)
                if port_out is not None and port_out not in ports_out:
                    ports_out.append(port_out)

        # route all ITEC ports
        itec.set_route(port_in, ports_out)
        # start or stop playing url stream
        stop_start_play(url_in)
        stop_start_send(urls_out)


config = Config()


def set_routes():
    """ Setup routes according settings (not taking into account setting auto_switch) """
    enabled_sources = [s for s in settings.sources if s.enabled]
    enabled_destinations = [d for d in settings.destinations if d.enabled]
    config.set_routes(enabled_sources, enabled_destinations)
    config.current_levels.clear()


def get_routes():
    """ Return the routes of the enabled IN ports as text """
    # TODO maybe it is better to return all ITEC IN ports, not only the enabled sources.
    result = f"Looking at usb port {itec_module.get_usb_port()}\n"
    if itec.serial is None:
        result += f"ITEC is not connected.\n"
        return result
    enabled_sources = [s for s in settings.sources if s.enabled]
    ports = list(set([get_IN_port(s) for s in enabled_sources]))
    result += "IN -> OUT\n"
    for p in ports:
        result += f"{p} -> {itec.get_route(p)}\n"
    return result


async def scan_ports():
    """ Continuously scan ports, measure audio level (dB's) and save result in config.
    This method only scans ITEC ports, not the url streams. """
    while True:
        try:
            # look only at enabled sources
            sources = [s for s in settings.sources if s.enabled]

            # cleanup config, deleting all source-ids which not exist
            source_ids = [s.id for s in sources]
            for source_id in list(config.current_levels.keys()):
                if not source_id in source_ids:
                    del config.current_levels[source_id]

            # measure inputlevel by communicating with itec
            for source in sources:
                port = settings.get_IN_port(source.port_url)
                if port is None:
                    port = settings.get_IN_port(settings.settings.port_IN_for_streams)

                if settings.is_IN_port(source.port_url):
                    port = settings.get_IN_port(source.port_url)
                    level = itec.get_input_level(port)
                    config.current_levels[source.id] = {'level': level, 'threshold': source.db_level, 'prio': source.scan_prio}
                elif settings.is_url(source.port_url):
                    if config.url_in == source.port_url:
                        # TODO check if this source is currenly streamed on the IN port
                        # only then it can be updated, ignore otherwise (will be done maybe in next loop)
                        port = settings.get_IN_port(settings.settings.port_IN_for_streams)
                        level = itec.get_input_level(port)
                        config.current_levels[source.id] = {'level': level, 'threshold': source.db_level, 'prio': source.scan_prio}

        except:
            pass
        await asyncio.sleep(2)


async def auto_switch():
    """
    Continuously check if a switch to another source is needed.

    """
    interval_seconds = 5
    while True:
        try:
            if settings.settings.enable_option_auto_switch and settings.settings.enable_auto_switch:
                # difficulty: one port is available to test input of all url-based-sources.
                # solution: switch between url-based-sources and measure level on same IN-port for each
                # drawback: not possible to auto-switch from one url to another

                # determine source_id which should be selected
                source_id = None
                prio = 0

                for s_id, v in config.current_levels.items():
                    level, threshold, source_prio = v['level'], v['threshold'], v['prio']
                    if source_prio > 0 and level >= threshold:
                        if prio == 0 or source_prio < prio:
                            source_id = s_id
                            prio = source_prio

                # routing is only needed if current selection is not source_id
                routing_needed = False
                source: Source = None
                if source_id is not None:
                    sources = [s for s in settings.sources if s.enabled]
                    for s in sources:
                        if s.id == source_id and not s.selected:
                            s.selected = True
                            routing_needed = True
                            source = s
                        elif s.id != source_id and s.selected:
                            s.selected = False
                            routing_needed = True

                if routing_needed:
                    msg = f"Auto switching to source '{source.name}'"
                    print(msg)
                    main_logger.info(msg)
                    settings.save()
                    set_routes()

        except:
            pass
        await asyncio.sleep(interval_seconds)
