"""Seriele poort: een timeout is tijdelijk en mag de bediening niet stilleggen.

Aanleiding (west, 2026-09-06): drie SerialTimeoutException's tijdens de
avonddienst. Geen hardwarefout -- geen USB-fouten of disconnects in dmesg -- maar
bus-contentie: de pl2303 praat in bulk-transfers en deelt op de Pi 3 een
full-speed segment met de USB-audiocodec, waarvan het isochrone verkeer voorrang
heeft. Een pakket van 5 bytes heeft ~2,6 ms zendtijd nodig, maar de timeout stond
op 50 ms, en bij een timeout gooide write_read de hele verbinding weg. Viel hij
twee keer binnen 5 seconden weg, dan hield get_serial() het heropenen nog eens tot
5 seconden tegen en gaven de endpoints 503 ("Tijdelijk geen bediening mogelijk").
"""
import datetime as dt

import pytest
import serial

from audio_controller import itec


class _FakeSerial:
    """Minimale serial.Serial-vervanger die opneemt wat er met hem gebeurt."""

    def __init__(self, write_exc=None):
        self.write_exc = write_exc
        self.writes = 0
        self.output_buffer_resets = 0
        self.input_buffer_resets = 0

    def write(self, packet):
        self.writes += 1
        if self.write_exc is not None:
            raise self.write_exc

    def read(self, n):
        return b""

    def reset_output_buffer(self):
        self.output_buffer_resets += 1

    def reset_input_buffer(self):
        self.input_buffer_resets += 1


def _itec(fake):
    obj = itec.ITEC.__new__(itec.ITEC)  # __init__ opent een echte poort
    obj.device_id = 0x01
    obj.serial = fake
    return obj


@pytest.fixture(autouse=True)
def _reset_backoff():
    itec._last_failed_open = None
    yield
    itec._last_failed_open = None


def test_timeout_houdt_de_poort_open_en_leegt_de_buffers():
    fake = _FakeSerial(write_exc=serial.SerialTimeoutException("Write timeout"))
    obj = _itec(fake)

    assert obj.write_read(0x80, 0xC1, 0) is None
    # poort blijft open: de volgende aanroep hoeft niet te heropenen
    assert obj.serial is fake
    # half verzonden pakket en oud antwoord zijn opgeruimd
    assert fake.output_buffer_resets == 1
    assert fake.input_buffer_resets == 1


def test_echte_fout_gooit_de_verbinding_wel_weg():
    fake = _FakeSerial(write_exc=serial.SerialException("device disappeared"))
    obj = _itec(fake)

    assert obj.write_read(0x80, 0xC1, 0) is None
    assert obj.serial is None


def test_timeout_waarbij_ook_legen_faalt_gooit_de_verbinding_weg():
    fake = _FakeSerial(write_exc=serial.SerialTimeoutException("Write timeout"))

    def kapot():
        raise OSError("port gone")

    fake.reset_output_buffer = kapot
    obj = _itec(fake)

    assert obj.write_read(0x80, 0xC1, 0) is None
    assert obj.serial is None


def test_tweede_poging_leegt_eerst_de_leesbuffer():
    # write lukt, maar read geeft geen ACK -> er volgt een tweede poging
    fake = _FakeSerial()
    obj = _itec(fake)

    assert obj.write_read(0x80, 0xC1, 0) is None
    assert fake.writes == 2
    assert fake.input_buffer_resets == 1


def test_geslaagde_open_wordt_niet_afgeremd(monkeypatch):
    """Twee keer achter elkaar heropenen mag, zolang het openen lukt."""
    geopend = []

    class _OK(_FakeSerial):
        def open(self):
            geopend.append(1)

    monkeypatch.setattr(itec.serial, "Serial", _OK)
    monkeypatch.setattr(itec, "get_usb_port", lambda: "/dev/ttyUSB0")

    assert itec.get_serial() is not None
    assert itec.get_serial() is not None
    assert len(geopend) == 2


def test_mislukte_open_wordt_wel_afgeremd(monkeypatch):
    """Een adapter die er niet is mag niet aanhoudend bestookt worden."""
    pogingen = []

    class _Kapot(_FakeSerial):
        def open(self):
            pogingen.append(1)
            raise serial.SerialException("no such device")

    monkeypatch.setattr(itec.serial, "Serial", _Kapot)
    monkeypatch.setattr(itec, "get_usb_port", lambda: "/dev/ttyUSB0")

    assert itec.get_serial() is None
    assert itec.get_serial() is None  # binnen het venster: niet nog eens proberen
    assert len(pogingen) == 1

    # na het venster mag het weer
    itec._last_failed_open = dt.datetime.utcnow() - dt.timedelta(seconds=6)
    assert itec.get_serial() is None
    assert len(pogingen) == 2


def test_timeouts_zijn_ruim_boven_de_zendtijd_van_een_pakket():
    # 5 bytes, 8N1, 19200 baud -> 5 * 10 / 19200 = 2,6 ms
    zendtijd = 5 * 10 / 19200
    assert itec.SERIAL_READ_TIMEOUT > 20 * zendtijd
    # de schrijftimeout is wat op west stuk liep, die mag het ruimst
    assert itec.SERIAL_WRITE_TIMEOUT > itec.SERIAL_READ_TIMEOUT


def test_leestimeout_blokkeert_de_event_loop_niet_langer_dan_een_scanronde():
    """scan_ports doet deze reads synchroon en draait elke 2 seconden.

    Per ronde hooguit twee seriele round-trips (de IN-poort en de lopende
    url-stream), elk met een tweede poging. Blijft het apparaat stil, dan mag dat
    de event loop niet langer bezet houden dan de scanronde zelf.
    """
    round_trips_per_ronde = 2
    pogingen_per_round_trip = 2
    scanronde = 2.0  # seconden, zie controller.scan_ports
    ergste_geval = round_trips_per_ronde * pogingen_per_round_trip * itec.SERIAL_READ_TIMEOUT
    assert ergste_geval < scanronde
