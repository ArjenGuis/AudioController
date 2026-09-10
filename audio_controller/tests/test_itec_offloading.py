"""Seriele I/O mag de event loop niet blokkeren, en mag nooit door elkaar lopen.

Aanleiding: alle listeners (5000 intern, 8080 extern) delen een event loop, en
scan_ports/set_routes/get_routes deden hun seriele I/O daar synchroon in. Een trage
of stille ITEC legde daarmee de hele server plat -- ook de camera-app en het
psalmbord-kioskscherm, die niets met de ITEC te maken hebben.

Alle ITEC-aanroepen gaan nu via itec.run() naar EEN vaste worker-thread. Een worker
in plaats van een pool is een bewuste keuze: dat serialiseert de opdrachten en houdt
ze in volgorde, zodat een route-wijziging en een niveaumeting elkaar niet half
kunnen overschrijven. Een slot per commando zou dat niet geven.

Er wordt geen echte poort geopend; ITEC.write_read wordt vervangen door een trage
namaakversie die vastlegt wanneer en op welke thread hij draaide.
"""
import asyncio
import threading
import time

import pytest
import tornado.ioloop

from audio_controller import controller, itec as itec_module, settings
from audio_controller.settings import Source, Destination


HOOFDTHREAD = None


class Recorder:
    """Vervangt write_read: traag, en legt thread + tijdvenster van elke aanroep vast."""

    def __init__(self, duur=0.05):
        self.duur = duur
        self.aanroepen = []          # (label, thread, start, eind)
        self.threads = set()
        self._lock = threading.Lock()
        self.label = "?"

    def write_read(self, command, r_value, value):
        start = time.monotonic()
        thread = threading.current_thread().name
        time.sleep(self.duur)
        eind = time.monotonic()
        with self._lock:
            self.threads.add(thread)
            self.aanroepen.append((self.label, thread, start, eind))
        return 0x00

    def overlapt_iets(self):
        """True als twee aanroepen elkaar in de tijd overlappen."""
        vensters = sorted((s, e) for _, _, s, e in self.aanroepen)
        return any(vensters[i][1] > vensters[i + 1][0] for i in range(len(vensters) - 1))


@pytest.fixture
def rec(monkeypatch):
    global HOOFDTHREAD
    HOOFDTHREAD = threading.current_thread().name
    r = Recorder()
    monkeypatch.setattr(itec_module.itec, "write_read", r.write_read)
    monkeypatch.setattr(itec_module.itec, "serial", object())  # "verbonden"
    monkeypatch.setattr(settings.settings, "port_IN_for_streams", "IN4")
    monkeypatch.setattr(settings.settings, "port_OUT_to_stream", "OUT4")
    monkeypatch.setattr(settings.settings, "mute_sound", False)
    monkeypatch.setattr(settings.settings, "connect_source_destination", True)
    return r


def run_sync(coro_fn):
    """Draai een coroutine in een echte Tornado-loop, zoals de applicatie doet.

    De loop wordt expliciet gesloten: Tornado 6.1 (de Pi) weigert een tweede IOLoop
    zolang de vorige nog 'current' is, terwijl 6.5 (de lokale venv) dat toestaat.
    Zonder dit gedragen deze tests zich lokaal anders dan op het apparaat.
    """
    loop = tornado.ioloop.IOLoop(make_current=True)
    try:
        return loop.run_sync(coro_fn)
    finally:
        loop.close(all_fds=False)


BRONNEN = [Source("A", True, "IN1", 1, -45, True, id=1),
           Source("B", True, "IN2", 0, -45, False, id=2)]
BESTEMMINGEN = [Destination("O1", True, "OUT1", True, id=1)]


def test_seriele_io_draait_nooit_op_de_event_loop_thread(rec, monkeypatch):
    monkeypatch.setattr(settings, "sources", BRONNEN)
    monkeypatch.setattr(settings, "destinations", BESTEMMINGEN)
    monkeypatch.setattr(controller.config, "apply_streams", lambda *a: None)

    run_sync(controller.set_routes)

    assert rec.aanroepen, "er is niets gemeten"
    assert HOOFDTHREAD not in rec.threads
    assert all(t.startswith("itec") for t in rec.threads), rec.threads


def test_alle_seriele_paden_gebruiken_dezelfde_ene_thread(rec, monkeypatch):
    monkeypatch.setattr(settings, "sources", BRONNEN)
    monkeypatch.setattr(settings, "destinations", BESTEMMINGEN)
    monkeypatch.setattr(controller.config, "apply_streams", lambda *a: None)

    async def alles():
        await controller.set_routes()
        await controller.get_routes()
        await itec_module.run(controller._read_levels, [1, 2])

    run_sync(alles)
    assert len(rec.threads) == 1, rec.threads


def test_event_loop_blijft_draaien_tijdens_seriele_io(rec, monkeypatch):
    """De kern van de fix: de loop moet ondertussen ander werk kunnen doen."""
    monkeypatch.setattr(settings, "sources", BRONNEN)
    monkeypatch.setattr(settings, "destinations", BESTEMMINGEN)
    monkeypatch.setattr(controller.config, "apply_streams", lambda *a: None)
    rec.duur = 0.10  # 3 routes -> ~0,3s seriele I/O

    ticks = 0

    async def alles():
        nonlocal ticks
        taak = asyncio.ensure_future(controller.set_routes())
        while not taak.done():
            await asyncio.sleep(0.005)
            ticks += 1
        await taak

    t0 = time.monotonic()
    run_sync(alles)
    duur = time.monotonic() - t0

    assert duur > 0.2, "de namaak-ITEC hoorde echt te blokkeren"
    # zonder de fix zou de loop hier geen enkele keer aan bod komen
    assert ticks > 10, f"loop kwam maar {ticks}x aan bod in {duur:.2f}s"


def test_route_wijziging_en_niveaumeting_lopen_niet_door_elkaar(rec, monkeypatch):
    monkeypatch.setattr(settings, "sources", BRONNEN)
    monkeypatch.setattr(settings, "destinations", BESTEMMINGEN)
    monkeypatch.setattr(controller.config, "apply_streams", lambda *a: None)
    rec.duur = 0.02

    async def alles():
        await asyncio.gather(
            controller.set_routes(),
            itec_module.run(controller._read_levels, [1, 2, 3]),
            controller.get_routes(),
        )

    run_sync(alles)
    assert not rec.overlapt_iets(), "twee seriele aanroepen overlapten in de tijd"


def test_twee_gelijktijdige_route_wijzigingen_lopen_niet_door_elkaar(rec, monkeypatch):
    """Het asyncio-slot in set_routes: plan A moet volledig af zijn voor plan B start."""
    monkeypatch.setattr(settings, "sources", BRONNEN)
    monkeypatch.setattr(settings, "destinations", BESTEMMINGEN)
    monkeypatch.setattr(controller.config, "apply_streams", lambda *a: None)
    rec.duur = 0.01

    volgorde = []

    origineel = controller.apply_routes

    def gelabeld(routes):
        volgorde.append(("start", rec.label))
        origineel(routes)
        volgorde.append(("eind", rec.label))

    monkeypatch.setattr(controller, "apply_routes", gelabeld)

    async def een(label):
        rec.label = label
        await controller.set_routes()

    async def alles():
        await asyncio.gather(een("A"), een("B"))

    run_sync(alles)

    # geen enkele "start" mag tussen een andere start en zijn eind vallen
    diepte = 0
    for soort, _ in volgorde:
        diepte += 1 if soort == "start" else -1
        assert diepte <= 1, f"route-wijzigingen overlapten: {volgorde}"


def test_routeslot_werkt_in_een_verse_event_loop(rec, monkeypatch):
    """Regressie: asyncio.Lock() bindt zich op Python 3.7 aan de loop van dat moment.

    Een slot op module-niveau lijkt te werken zolang het onbetwist blijft -- die
    route raakt de binding niet eens aan -- maar gooit bij de eerste ECHTE botsing
    "got Future attached to a different loop". Deze test botst opzettelijk, in een
    verse loop, want dat is het enige wat het verschil aantoont.
    """
    monkeypatch.setattr(settings, "sources", BRONNEN)
    monkeypatch.setattr(settings, "destinations", BESTEMMINGEN)
    monkeypatch.setattr(controller.config, "apply_streams", lambda *a: None)
    rec.duur = 0.02

    async def botsen():
        await asyncio.gather(controller.set_routes(), controller.set_routes())

    for _ in range(3):  # elke ronde een nieuwe loop
        run_sync(botsen)


def test_startpad_werkt_zonder_draaiende_event_loop(rec, monkeypatch):
    """__main__ zet de routes voordat de loop start; dat mag niet stukgaan."""
    monkeypatch.setattr(settings, "sources", BRONNEN)
    monkeypatch.setattr(settings, "destinations", BESTEMMINGEN)
    monkeypatch.setattr(controller.config, "apply_streams", lambda *a: None)

    controller.set_routes_blocking()

    assert rec.aanroepen
    # bij het opstarten mag het wel op de hoofdthread: er is nog geen loop om te blokkeren
    assert rec.threads == {HOOFDTHREAD}


def test_scan_ports_meet_via_de_itec_thread(rec, monkeypatch):
    monkeypatch.setattr(settings, "sources", BRONNEN)
    controller.config.url_in = None

    async def een_ronde():
        te_meten = controller.ports_to_scan(BRONNEN)
        levels = await itec_module.run(controller._read_levels, [p for _, p in te_meten])
        return te_meten, levels

    te_meten, levels = run_sync(een_ronde)
    assert len(te_meten) == 2 and len(levels) == 2
    assert HOOFDTHREAD not in rec.threads
