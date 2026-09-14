"""Welk ONVIF-profiel de bediening gebruikt.

Aanleiding: tijdens de dienst liep het camerabeeld in de bediening minuten
achter. De hoofdstream (hoge resolutie/bitrate) komt sneller binnen dan de
browser hem kan verwerken; het verschil verdwijnt in de buffer en loopt de hele
dienst op -- bij de tussenzang zo'n vier minuten. De substream is lichter en
juist voor dit soort gebruik bedoeld.

Het profiel hard op GetProfiles()[1] zetten lost dat op bij een camera met twee
profielen, maar laat connect() met een IndexError stuklopen bij een camera die
er maar een aanbiedt -- en dat wordt in de app een 'Verbinding mislukt'.
"""
import pytest

from audio_controller import camera


def _profile(token, width=None, height=None):
    """Namaak-ONVIF-profiel; zonder afmetingen meldt de camera geen resolutie."""
    prof = type("Profile", (), {})()
    prof.token = token
    prof._x_Name = token
    if width is not None:
        res = type("Resolution", (), {})()
        res.Width, res.Height = width, height
        enc = type("VideoEncoderConfiguration", (), {})()
        enc.Resolution = res
        prof.VideoEncoderConfiguration = enc
    return prof


def test_substream_is_chosen_over_the_main_stream():
    main = _profile("main", 3840, 2160)
    sub = _profile("sub", 704, 576)
    assert camera.select_stream_profile([main, sub]) is sub


def test_the_lightest_stream_wins_regardless_of_the_order():
    sub = _profile("sub", 704, 576)
    main = _profile("main", 1920, 1080)
    assert camera.select_stream_profile([sub, main]) is sub


def test_a_camera_with_one_profile_keeps_working():
    # de reden dat GetProfiles()[1] niet kan: dit gaf een IndexError, en daarmee
    # 'Verbinding met ... mislukt' voor de hele camera
    only = _profile("main", 1920, 1080)
    assert camera.select_stream_profile([only]) is only


def test_without_resolutions_the_second_profile_is_used():
    # ONVIF zet de hoofdstream doorgaans eerst en de substream tweede; meldt de
    # camera geen resoluties, dan volgen we die volgorde
    first, second = _profile("main"), _profile("sub")
    assert camera.select_stream_profile([first, second]) is second


def test_without_resolutions_and_one_profile_that_profile_is_used():
    only = _profile("main")
    assert camera.select_stream_profile([only]) is only


def test_a_profile_without_resolution_never_beats_a_measured_one():
    # anders zou een profiel dat zijn resolutie niet meldt de keuze bepalen
    unknown = _profile("unknown")
    sub = _profile("sub", 704, 576)
    main = _profile("main", 1920, 1080)
    assert camera.select_stream_profile([unknown, main, sub]) is sub


def test_no_profiles_at_all_is_no_profile():
    assert camera.select_stream_profile([]) is None


# --- via connect(), zoals de app het gebruikt ----------------------------

class _FakeMedia:
    def __init__(self, profiles):
        self.profiles = profiles

    def GetProfiles(self):
        return self.profiles


class _FakeCam:
    def __init__(self, profiles):
        self.profiles = profiles

    def create_media_service(self):
        return _FakeMedia(self.profiles)

    create_ptz_service = create_media_service
    create_devicemgmt_service = create_media_service


@pytest.fixture
def onvif_with(monkeypatch):
    def install(profiles):
        monkeypatch.setattr(camera, "ONVIFCamera",
                            lambda *a, **kw: _FakeCam(profiles))
    return install


def _cam():
    return camera.Camera(name="Kerk", url_intern="10.0.0.5", url_extern="x",
                         port_http=80, port_onvif=2000, port_ws=8088,
                         username="u", password="p")


def test_connect_selects_the_substream(onvif_with):
    onvif_with([_profile("main", 3840, 2160), _profile("sub", 704, 576)])
    cam = _cam()
    cam.connect()
    assert cam._profile.token == "sub"


def test_connect_survives_a_camera_with_a_single_profile(onvif_with):
    onvif_with([_profile("main", 1920, 1080)])
    cam = _cam()
    cam.connect()                      # geen IndexError -> geen 'verbinding mislukt'
    assert cam._profile.token == "main"


def test_connect_reports_a_camera_without_profiles_as_unreachable(onvif_with):
    onvif_with([])
    with pytest.raises(ConnectionError):
        _cam().connect()
