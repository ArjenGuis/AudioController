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
