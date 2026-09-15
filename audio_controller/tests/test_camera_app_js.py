"""Structural guards for the camera app's own frontend (static/js/camera.js).

camera.js is plain jQuery, served as-is and never exercised by the rest of the
suite. The bug these guard against: the "already logged in" and "just logged in"
paths each had their own show-list, they drifted apart, and the form path stopped
showing #live -- so after a fresh login the video stayed invisible until a page
refresh (visible only when the camera was unreachable, because that error path
does its own $('#live').show()).
"""
import re
from pathlib import Path

CAMERA_JS = (Path(__file__).resolve().parent.parent / "audio_controller"
             / "static" / "js" / "camera.js")


def _source():
    return CAMERA_JS.read_text(encoding="utf-8")


def test_both_login_paths_share_one_show_helper():
    src = _source()
    assert "function showLoggedIn(" in src
    # both branches of getLogin (cookie login and form login) must call it
    assert len(re.findall(r"showLoggedIn\(", src)) == 3  # 1 definition + 2 call sites


def test_logged_in_view_shows_the_live_container():
    # #live holds the <video>; without it the stream plays into a hidden box
    src = _source()
    body = src.split("function showLoggedIn(", 1)[1].split("\n\t}", 1)[0]
    assert "#live" in body, "showLoggedIn must show the #live container"


def test_username_comes_from_the_server_not_the_input_field():
    # login is case-insensitive: typing "Arjen" logs into "arjen". The UI (and the
    # prefilled "Wijzigen" form, which posts to setUser and would RENAME the
    # account) must use the canonical name from the login response.
    src = _source()
    assert "setUsername( $('#login #current-username').val() )" not in src
    assert "showLoggedIn( $response.username )" in src


# --- de SPA-camerapagina (transcrypt), zelfde soort bewaking ---------------
# Ook deze code draait nergens in de suite. De bugs die dit afdekt: getLive
# antwoordt met success=True en uri=False als de camera geen stream-URL geeft,
# en de pagina plakte dat aan elkaar tot "ws://host:8088false"; de foutmelding
# las een 'error'-sleutel uit die de handler niet stuurt, dus er stond letterlijk
# "undefined" op het scherm.

PAGE_CAMERA = (Path(__file__).resolve().parents[2] / "transcrypt" / "python"
               / "pages" / "page_camera.py")


def test_spa_checks_the_stream_uri_before_building_a_websocket_url():
    src = PAGE_CAMERA.read_text(encoding="utf-8")
    assert "if uri['success'] and uri['uri']:" in src


def test_spa_does_not_print_an_error_key_the_server_never_sends():
    src = PAGE_CAMERA.read_text(encoding="utf-8")
    assert "uri['error']" not in src


# --- camera.js: een camera die antwoordt maar faalt, moet zichtbaar zijn ---

def test_an_unexpected_camera_error_is_shown_instead_of_an_empty_panel():
    src = _source()
    assert "$camError" in src
    # de tak voor een err die niet 'connection' is
    assert "} else if( $response.err ){" in src
    # en renderLiveAlert toont hem
    body = src.split("function renderLiveAlert(", 1)[1].split("\n\t}", 1)[0]
    assert "$camError" in body
