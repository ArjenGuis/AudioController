"""Welk ONVIF-profiel de bediening gebruikt.

Aanleiding: tijdens de dienst liep het camerabeeld in de bediening minuten
achter. De hoofdstream (hoge resolutie/bitrate) komt sneller binnen dan de
browser hem kan verwerken; het verschil verdwijnt in de buffer en loopt de hele
dienst op -- bij de tussenzang zo'n vier minuten. De substream is lichter en
juist voor dit soort gebruik bedoeld.

Twee dingen gaan mis als je het profiel hard op GetProfiles()[1] zet:

 - een camera die maar een profiel aanbiedt geeft een IndexError, en dat wordt
   in de app 'Verbinding mislukt' voor die hele camera;
 - het gekozen profiel ging ook naar de PTZ-opdrachten (presets, bewegen),
   terwijl ONVIF niet voorschrijft dat een substream een PTZ-configuratie heeft.

Beeld en bediening staan daarom los van elkaar: PTZ blijft op het hoofdprofiel,
alleen de stream-URL volgt de substream.
"""
import pytest

from audio_controller import camera


def _profile(token, width=None, height=None):
    """Namaak-ONVIF-profiel; zonder afmetingen meldt de camera geen resolutie."""
    prof = type("Profile", (), {})()
    prof.token = token
    if width is not None:
        res = type("Resolution", (), {})()
        res.Width, res.Height = width, height
        enc = type("VideoEncoderConfiguration", (), {})()
        enc.Resolution = res
        prof.VideoEncoderConfiguration = enc
    return prof


# --- de keuze zelf --------------------------------------------------------

def test_substream_is_chosen_over_the_main_stream():
    main = _profile("main", 3840, 2160)
    sub = _profile("sub", 704, 576)
    assert camera.select_stream_profile([main, sub]) is sub


def test_the_substream_wins_regardless_of_the_order():
    sub = _profile("sub", 704, 576)
    main = _profile("main", 1920, 1080)
    assert camera.select_stream_profile([sub, main]) is sub


def test_a_third_even_lighter_profile_is_not_chosen():
    # veel camera's bieden naast main en sub nog een 'mobile'-profiel aan. Dat is
    # te grof om het beeld mee uit te kaderen: we willen de op een na zwaarste
    # stream, niet de allerlichtste.
    main = _profile("main", 1920, 1080)
    sub = _profile("sub", 704, 576)
    mobile = _profile("mobile", 352, 288)
    assert camera.select_stream_profile([main, sub, mobile]) is sub


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


def test_an_incomplete_set_of_resolutions_falls_back_to_the_onvif_order():
    # een half gemeten lijst is geen basis om op te sorteren: dan zou een profiel
    # dat zijn resolutie niet meldt de keuze bepalen
    unknown = _profile("unknown")
    sub = _profile("sub", 704, 576)
    assert camera.select_stream_profile([unknown, sub]) is sub


def test_no_profiles_at_all_is_no_profile():
    assert camera.select_stream_profile([]) is None


# --- via connect(), zoals de app het gebruikt ----------------------------

class _FakeMedia:
    def __init__(self, profiles):
        self.profiles = profiles
        self.stream_requests = []

    def GetProfiles(self):
        return self.profiles

    def create_type(self, _name):
        return type("Request", (), {})()

    def GetStreamUri(self, request):
        self.stream_requests.append(request.ProfileToken)
        uri = type("Uri", (), {})()
        uri.Uri = "rtsp://10.0.0.5:554/{}/av0".format(request.ProfileToken)
        return uri


class _FakeCam:
    def __init__(self, profiles):
        self.media = _FakeMedia(profiles)

    def create_media_service(self):
        return self.media

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


def test_the_video_comes_from_the_substream(onvif_with):
    onvif_with([_profile("main", 3840, 2160), _profile("sub", 704, 576)])
    cam = _cam()
    cam.connect()
    assert cam.get_stream_uri() == "/sub/av0"


def test_ptz_keeps_using_the_main_profile(onvif_with):
    # een substream hoeft geen PTZ-configuratie te hebben; gaat de bediening
    # daar toch naartoe, dan geeft de camera een SOAP-fout en staat de operator
    # zonder presets en zonder melding
    onvif_with([_profile("main", 3840, 2160), _profile("sub", 704, 576)])
    cam = _cam()
    cam.connect()
    assert cam._profile.token == "main"


def test_connect_survives_a_camera_with_a_single_profile(onvif_with):
    onvif_with([_profile("main", 1920, 1080)])
    cam = _cam()
    cam.connect()                      # geen IndexError -> geen 'verbinding mislukt'
    assert cam._profile.token == "main"
    assert cam.get_stream_uri() == "/main/av0"


def test_connect_reports_a_camera_without_profiles_as_unreachable(onvif_with):
    onvif_with([])
    with pytest.raises(ConnectionError):
        _cam().connect()
