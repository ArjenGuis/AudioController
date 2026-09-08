"""De plan/uitvoer-splitsing mag GEEN ander gedrag opleveren dan de oude code.

Config.update_sources_destinations deed het bepalen en het uitvoeren door elkaar,
waardoor de blokkerende seriele opdrachten niet van de event loop af konden. Dat is
nu gesplitst in plan_sources_destinations() (bepaalt, doet niets) en apply_routes()
/ apply_streams() (voeren uit). Deze test draait de ORIGINELE implementatie als
referentie naast de nieuwe, over alle takken van de beslisboom, en eist dat de
reeks set_route-aanroepen en de url-doelen exact gelijk zijn -- inclusief volgorde,
want de ITEC krijgt ze in die volgorde.
"""
import itertools

import pytest

from audio_controller import controller, settings
from audio_controller.settings import Source, Destination


# --- de originele implementatie, letterlijk overgenomen uit git HEAD ------------
# (alleen itec.set_route vervangen door registratie in een lijst)

def origineel(cfg, sources, destinations, opgenomen):
    def set_route(p, bus):
        opgenomen.append((p, list(bus)))

    def route_all_to_null():
        ports = [controller.get_IN_port(s) for s in cfg.sources]
        for p in ports:
            set_route(p, [])

    resultaat = {"url_in": None, "urls_out": []}

    def stop_all():
        route_all_to_null()
        resultaat["url_in"] = None
        resultaat["urls_out"] = []

    def disable_unselected_sources(selected_port):
        ports = [controller.get_IN_port(s) for s in cfg.sources if not s.selected]
        for p in ports:
            if p != selected_port:
                set_route(p, [])

    cfg.sources = sources
    cfg.destinations = destinations

    if not settings.settings.connect_source_destination or not destinations:
        stop_all()
        return resultaat

    selected_source = cfg.get_selected_source()
    if selected_source is None:
        stop_all()
        return resultaat

    port_in, url_in = cfg.get_input(selected_source)
    resultaat["url_in"] = url_in

    disable_unselected_sources(port_in)
    ports_out, urls_out = cfg.get_outputs()

    if settings.settings.mute_sound:
        route_all_to_null()
    else:
        set_route(port_in, ports_out)

    resultaat["urls_out"] = urls_out
    return resultaat


# --- scenario's ----------------------------------------------------------------

URL_A = "http://voorbeeld/een"
URL_B = "http://voorbeeld/twee"


def _bronnen(variant):
    if variant == "poort_geselecteerd":
        return [Source("A", True, "IN1", 1, -45, True, id=1),
                Source("B", True, "IN2", 0, -45, False, id=2),
                Source("C", True, "IN3", 0, -45, False, id=3)]
    if variant == "url_geselecteerd":
        return [Source("A", True, "IN1", 1, -45, False, id=1),
                Source("U", True, URL_A, 0, -45, True, id=2),
                Source("B", True, "IN2", 0, -45, False, id=3)]
    if variant == "niets_geselecteerd":
        return [Source("A", True, "IN1", 1, -45, False, id=1),
                Source("B", True, "IN2", 0, -45, False, id=2)]
    if variant == "alles_geselecteerd":
        return [Source("A", True, "IN1", 1, -45, True, id=1),
                Source("B", True, "IN2", 0, -45, True, id=2)]
    if variant == "geen":
        return []
    raise AssertionError(variant)


def _bestemmingen(variant):
    if variant == "poorten":
        return [Destination("O1", True, "OUT1", True, id=1),
                Destination("O2", True, "OUT2", True, id=2),
                Destination("O3", True, "OUT3", False, id=3)]
    if variant == "url":
        return [Destination("S", True, URL_B, True, id=1)]
    if variant == "poort_en_url":
        return [Destination("O1", True, "OUT1", True, id=1),
                Destination("S", True, URL_B, True, id=2)]
    if variant == "niets_geselecteerd":
        return [Destination("O1", True, "OUT1", False, id=1)]
    if variant == "geen":
        return []
    raise AssertionError(variant)


BRONVARIANTEN = ["poort_geselecteerd", "url_geselecteerd", "niets_geselecteerd",
                 "alles_geselecteerd", "geen"]
BESTEMMINGSVARIANTEN = ["poorten", "url", "poort_en_url", "niets_geselecteerd", "geen"]


@pytest.mark.parametrize(
    "bron,bestemming,mute,verbinden",
    list(itertools.product(BRONVARIANTEN, BESTEMMINGSVARIANTEN, [False, True], [True, False])),
)
def test_plan_is_gelijk_aan_de_oude_implementatie(bron, bestemming, mute, verbinden, monkeypatch):
    monkeypatch.setattr(settings.settings, "mute_sound", mute)
    monkeypatch.setattr(settings.settings, "connect_source_destination", verbinden)
    monkeypatch.setattr(settings.settings, "port_IN_for_streams", "IN4")
    monkeypatch.setattr(settings.settings, "port_OUT_to_stream", "OUT4")

    # referentie
    cfg_oud = controller.Config()
    opgenomen = []
    ref = origineel(cfg_oud, _bronnen(bron), _bestemmingen(bestemming), opgenomen)

    # nieuw
    cfg_nieuw = controller.Config()
    routes, url_in, urls_out = cfg_nieuw.plan_sources_destinations(
        _bronnen(bron), _bestemmingen(bestemming))

    assert routes == opgenomen, f"andere ITEC-opdrachten bij {bron}/{bestemming}/mute={mute}/verbind={verbinden}"
    assert url_in == ref["url_in"]
    assert urls_out == ref["urls_out"]


def test_plan_doet_geen_enkele_seriele_aanroep(monkeypatch):
    """Plannen moet volledig vrij van I/O zijn, anders blokkeert het alsnog de loop."""
    aanroepen = []
    monkeypatch.setattr(controller.itec, "write_read",
                        lambda *a, **k: aanroepen.append(a) or None)
    monkeypatch.setattr(settings.settings, "port_IN_for_streams", "IN4")
    monkeypatch.setattr(settings.settings, "port_OUT_to_stream", "OUT4")

    cfg = controller.Config()
    cfg.plan_sources_destinations(_bronnen("poort_geselecteerd"), _bestemmingen("poorten"))
    assert aanroepen == []


def test_ports_to_scan_kiest_dezelfde_poorten_als_voorheen(monkeypatch):
    """scan_ports koos de poorten inline; dat zit nu in ports_to_scan()."""
    monkeypatch.setattr(settings.settings, "port_IN_for_streams", "IN4")
    bronnen = _bronnen("url_geselecteerd")
    controller.config.url_in = URL_A

    # oude keuzelogica, letterlijk uit git HEAD
    verwacht = []
    for source in bronnen:
        if settings.is_IN_port(source.port_url):
            verwacht.append((source, settings.get_IN_port(source.port_url)))
        elif settings.is_url(source.port_url):
            if controller.config.url_in == source.port_url:
                verwacht.append((source, settings.get_IN_port(settings.settings.port_IN_for_streams)))

    assert controller.ports_to_scan(bronnen) == verwacht
    controller.config.url_in = None
