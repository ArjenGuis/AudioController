
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
    """ 
    Holds configuration, which consists of connections from input to output ports.
    """

    def __init__(self):
        self.current_levels = {}  # key = source-id, value = dict (keys: 'level', 'threshold', and 'prio')
        self.send_to_urls = stream.get_url_sender()
        self.read_from_url = stream.get_url_reader()
        self.sources = None
        self.destinations = None
        self.url_in = None  # url currently streamed onto the IN port (used by scan_ports); None if none

    def routes_all_to_null(self):
        """ route all IN ports of itec to null, meaning no sound will go through """
        return [(get_IN_port(s), []) for s in self.sources]

    def get_selected_source(self):
        for source in self.sources:
            if source.selected:
                return source
        return None

    def routes_disable_unselected_sources(self, selected_port):
        # disable all IN ports which are not selected
        ports = [get_IN_port(s) for s in self.sources if not s.selected]
        return [(p, []) for p in ports if p != selected_port]

    def get_input(self, selected_source):
        # determine all ports and urls for in and out
        port_in: int = None
        url_in: str = None
        
        port_in = settings.get_IN_port(selected_source.port_url)
        if port_in is None:
            # selected source is not a port, but an url
            port_in = settings.get_IN_port(settings.settings.port_IN_for_streams)
            url_in = selected_source.port_url
        
        return port_in, url_in

    def get_outputs(self):
        """
        Select all OUT ports which must get route (from input), and select urls to which audio must be send.
        """
        ports_out: List[int] = []
        urls_out: List[str] = []
        for d in self.destinations:
            if d.selected:
                port_out = settings.get_OUT_port(d.port_url_file)
                if port_out is None:
                    port_out = settings.get_OUT_port(settings.settings.port_OUT_to_stream)
                    if port_out is not None:
                        urls_out.append(d.port_url_file)
                if port_out is not None and port_out not in ports_out:
                    ports_out.append(port_out)
        return ports_out, urls_out

    def plan_sources_destinations(self, sources: List[Source], destinations: List[Destination]):
        """Bepaal wat er moet gebeuren, zonder I/O te doen.

        Levert (routes, url_in, urls_out): de ITEC-route-opdrachten in de volgorde
        waarin ze uitgevoerd moeten worden, plus de url-stream-doelen. Los van het
        uitvoeren, zodat de seriele opdrachten in een keer naar de ITEC-thread
        kunnen en het ffmpeg-werk op de hoofdthread blijft (dat forkt processen;
        forken vanuit een worker-thread is een deadlock-risico).

        url_in wordt hier al vastgelegd, niet pas bij apply_streams: scan_ports
        leest hem, en tussen plannen en uitvoeren zit nu een await. Zo kan er geen
        scanronde tussendoor glippen die nog de vorige stream meet.
        """
        self.sources = sources
        self.destinations = destinations

        stop = (not settings.settings.connect_source_destination or not destinations
                or self.get_selected_source() is None)
        if stop:
            self.url_in = None
            return self.routes_all_to_null(), None, []

        selected_source = self.get_selected_source()
        port_in, url_in = self.get_input(selected_source)
        self.url_in = url_in  # remember which url (if any) is on the IN port, for scan_ports (C1)

        routes = self.routes_disable_unselected_sources(port_in)
        ports_out, urls_out = self.get_outputs()

        if settings.settings.mute_sound:
            # Muting only affects the itec ports.
            # The url streams will be kept intact
            routes += self.routes_all_to_null()
        else:
            routes.append((port_in, ports_out))
        return routes, url_in, urls_out

    def apply_streams(self, url_in, urls_out):
        """Start of stop de url-streams. Hoort op de hoofdthread te draaien: dit
        forkt ffmpeg-processen, en forken vanuit een worker-thread kan vastlopen."""
        self.read_from_url.update_url(url_in)
        self.send_to_urls.update_urls(urls_out)


config = Config()

# set_routes() is niet langer atomair: hij geeft de controle af terwijl de ITEC-thread
# de routes zet. Zonder slot zouden twee gelijktijdige aanroepen (een bediener die
# opslaat en auto_switch) elkaars plan half kunnen uitvoeren.
_routes_lock = None
_routes_lock_loop = None


def _get_routes_lock():
    """Het slot, aangemaakt in de draaiende loop.

    Op Python 3.7 (de Pi) bindt asyncio.Lock() zich bij het aanmaken aan de dan
    actuele event loop. Een slot op module-niveau lijkt te werken -- de onbetwiste
    route raakt die binding niet eens aan -- maar zodra hij voor het eerst ECHT
    betwist wordt gooit hij "got Future attached to a different loop". Precies in
    het zeldzame geval waarvoor het slot bestaat. Dus lui aanmaken.
    """
    global _routes_lock, _routes_lock_loop
    loop = asyncio.get_event_loop()
    if _routes_lock is None or _routes_lock_loop is not loop:
        _routes_lock = asyncio.Lock()
        _routes_lock_loop = loop
    return _routes_lock


def apply_routes(routes):
    """Zet de gegeven ITEC-routes. Blokkeert; draait op de seriele worker-thread."""
    for channel, bus in routes:
        itec.set_route(channel, bus)


def _plan_routes():
    """Het plan voor de huidige instellingen. Geen I/O."""
    enabled_sources = [s for s in settings.sources if s.enabled]
    enabled_destinations = [d for d in settings.destinations if d.enabled]
    return config.plan_sources_destinations(enabled_sources, enabled_destinations)


def _finish_routes(url_in, urls_out):
    """Afronding na de ITEC-opdrachten. Hoort op de hoofdthread te draaien."""
    config.apply_streams(url_in, urls_out)
    config.current_levels.clear()


async def set_routes():
    """ Setup routes according settings (not taking into account setting auto_switch) """
    async with _get_routes_lock():
        routes, url_in, urls_out = _plan_routes()
        await itec_module.run(apply_routes, routes)
        _finish_routes(url_in, urls_out)


def set_routes_blocking():
    """set_routes() voor het opstarten, wanneer de event loop nog niet draait.

    Deelt bewust dezelfde stappen als set_routes(), zodat de twee niet uit elkaar
    kunnen lopen; alleen het uitvoeren gebeurt hier op de aanroepende thread.
    """
    routes, url_in, urls_out = _plan_routes()
    apply_routes(routes)
    _finish_routes(url_in, urls_out)


def _read_routes(ports):
    """Lees de routes van de gegeven poorten. Draait op de seriele worker-thread."""
    return [(p, itec.get_route(p)) for p in ports]


async def get_routes():
    """ Return the routes of the enabled IN ports as text """
    # TODO maybe it is better to return all ITEC IN ports, not only the enabled sources.
    result = f"Looking at usb port {itec_module.get_usb_port()}\n"
    if itec.serial is None:
        result += f"ITEC is not connected.\n"
        return result
    enabled_sources = [s for s in settings.sources if s.enabled]
    ports = list(set([get_IN_port(s) for s in enabled_sources]))
    result += "IN -> OUT\n"
    for p, route in await itec_module.run(_read_routes, ports):
        result += f"{p} -> {route}\n"
    return result


def ports_to_scan(sources):
    """Welke (source, IN-poort) gemeten moeten worden. Leest niets uit, doet geen I/O."""
    result = []
    for source in sources:
        if settings.is_IN_port(source.port_url):
            result.append((source, settings.get_IN_port(source.port_url)))
        elif settings.is_url(source.port_url) and config.url_in == source.port_url:
            # TODO check if this source is currenly streamed on the IN port
            # only then it can be updated, ignore otherwise (will be done maybe in next loop)
            result.append((source, settings.get_IN_port(settings.settings.port_IN_for_streams)))
    return result


def _read_levels(ports):
    """Lees de niveaus van de gegeven poorten. Draait op de seriele worker-thread."""
    return [itec.get_input_level(p) for p in ports]


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
            # De hele ronde gaat in EEN opdracht naar de seriele thread: dat houdt de
            # event loop vrij (alle listeners delen er een) en de meting binnen een
            # ronde bij elkaar, zonder dat er een route-wijziging tussendoor glipt.
            te_meten = ports_to_scan(sources)
            if te_meten:
                levels = await itec_module.run(_read_levels, [p for _, p in te_meten])
                for (source, _), level in zip(te_meten, levels):
                    config.current_levels[source.id] = {'level': level, 'threshold': source.db_level, 'prio': source.scan_prio}

        except Exception as e:
            # log instead of silently swallowing (C2); keep the loop alive
            main_logger.warning(f"scan_ports error: {e}")
        await asyncio.sleep(2)


def auto_switch_interval_seconds(timeout_minutes) -> int:
    """Seconds between auto_switch passes, with a 1s floor so a zero timeout can
    never turn the loop into a 100%-CPU busy loop. (P1)"""
    try:
        return max(1, int(timeout_minutes) * 60)
    except (TypeError, ValueError):
        return 60


async def auto_switch():
    """
    Continuously check if a switch to another source is needed.

    """
    interval_seconds = auto_switch_interval_seconds(settings.settings.timeout_auto_switch)
    while True:
        try:
            if settings.settings.enable_option_auto_switch and settings.settings.enable_auto_switch:
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
                    sources = [s for s in settings.sources if s.enabled and s.scan_prio >= 0]
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
                    await set_routes()

        except Exception as e:
            # log instead of silently swallowing (C2); keep the loop alive
            main_logger.warning(f"auto_switch error: {e}")
        await asyncio.sleep(interval_seconds)
