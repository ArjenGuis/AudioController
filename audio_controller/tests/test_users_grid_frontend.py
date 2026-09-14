"""Unit tests for the SPA users-grid rules (issue #23).

`transcrypt/python/users_grid.py` holds the grid's decision logic as plain
Python so it can be tested here; the Transcrypt page (pages/page_admin.py) only
wires it to the DOM. pytest never runs the compiled main.js, which is exactly
how these bugs shipped:

 - `self.users = await post(setUsers, ...)` stored the SERVER'S ERROR OBJECT in
   the model, so the next save posted {"users": {"success": false, ...}} and the
   grid died with "self.data is not iterable";
 - the error was never shown;
 - "Toevoegen" seeded the literal password "password", which the server rejects
   as weak on the first onchange of the new row.
"""
import importlib.util
from pathlib import Path

import pytest

_MODULE = (Path(__file__).resolve().parents[2] / "transcrypt" / "python"
           / "users_grid.py")


def _load():
    spec = importlib.util.spec_from_file_location("users_grid", _MODULE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


users_grid = _load()


def _row(username, password="", orig=None, admin=False, camera=False):
    row = {"username": username, "password": password, "admin": admin,
           "camera": camera}
    if orig is not None:
        row["orig_username"] = orig
    return row


# --- new rows -------------------------------------------------------------

def test_new_row_has_no_default_password():
    # "password" is rejected by the server as weak (is_weak_password), so a new
    # row must start empty and be filled in by the admin.
    row = users_grid.new_row()
    assert row["password"] == ""
    assert row["username"] == ""


def test_new_row_has_every_field_the_server_expects():
    # the old helper was called with 2 of its 4 arguments, so admin/camera were
    # undefined and dropped from the JSON payload entirely.
    assert set(users_grid.new_row()) == {"username", "password", "admin", "camera"}


# --- when may the grid post? ---------------------------------------------

def test_incomplete_new_row_is_not_posted():
    # the grid saves on every onchange; typing only the username must not fire a
    # save that the server can only refuse.
    rows = [_row("beheer", orig="beheer"), _row("pietjepuk")]
    assert users_grid.validate(rows) != ""


def test_new_row_with_username_and_password_is_posted():
    rows = [_row("beheer", orig="beheer"),
            _row("pietjepuk", password="ditiseenmoeilijkwachtwoord")]
    assert users_grid.validate(rows) == ""


def test_renamed_row_may_be_posted_without_a_password():
    # issue #23 testcase 2: a rename keeps the stored password (the server
    # matches on orig_username), so no password is required.
    rows = [_row("kostert", orig="koster", camera=True)]
    assert users_grid.validate(rows) == ""


def test_empty_username_is_not_posted():
    rows = [_row("", password="ditiseenmoeilijkwachtwoord")]
    assert users_grid.validate(rows) != ""


def test_duplicate_username_is_caught_before_posting():
    rows = [_row("beheer", orig="beheer"), _row("Beheer", password="Sterk!wachtwoord9")]
    assert users_grid.validate(rows) != ""


# --- what the grid does with the server's answer --------------------------

def test_a_successful_save_replaces_the_model_with_the_returned_list():
    rows = [_row("koster", orig="koster")]
    server = [{"username": "koster", "orig_username": "koster", "password": "",
               "admin": False, "camera": True, "must_change_password": False}]
    new_rows, error = users_grid.apply_result(rows, server)
    assert new_rows == server
    assert error == ""


def test_a_rejected_save_keeps_the_model_and_reports_the_error():
    # THE bug: the error object was assigned to self.users, so the next save
    # posted {"users": {"success": false, ...}} -> "Ongeldige gebruikerslijst".
    rows = [_row("kostert", orig="koster")]
    result = {"success": False, "error": "Kies een sterker wachtwoord"}
    new_rows, error = users_grid.apply_result(rows, result)
    assert new_rows == rows
    assert error == "Kies een sterker wachtwoord"


def test_a_rejected_save_without_an_error_text_still_reports_something():
    rows = [_row("koster", orig="koster")]
    new_rows, error = users_grid.apply_result(rows, {"success": False})
    assert new_rows == rows
    assert error != ""


def test_a_login_required_answer_does_not_become_the_model():
    rows = [_row("koster", orig="koster")]
    new_rows, error = users_grid.apply_result(
        rows, {"success": False, "LoginException": "Please login first"})
    assert new_rows == rows
    assert error != ""


# --- the page must actually use these rules -------------------------------
# pytest never runs the compiled main.js, so guard the wiring in the source
# (same approach as tests/test_camera_app_js.py).

_PAGE_ADMIN = (Path(__file__).resolve().parents[2] / "transcrypt" / "python"
               / "pages" / "page_admin.py")


def _users_section():
    src = _PAGE_ADMIN.read_text(encoding="utf-8")
    return src.split("class Users(", 1)[1].split("\nclass ", 1)[0]


def test_the_grid_never_stores_the_answer_of_a_save_unchecked():
    # `self.users = await utils.post(...)` is the bug: an error object became
    # the user list and was posted back on the next change.
    body = _users_section()
    assert "self.users = await utils.post" not in body
    assert "users_grid.apply_result" in body


def test_the_grid_shows_what_went_wrong():
    body = _users_section()
    assert "alert-danger" in body
    assert "show_error(" in body


def test_new_rows_come_from_the_shared_helper():
    body = _users_section()
    assert "users_grid.new_row()" in body
    assert '"password"' not in body.split("def add_item", 1)[1].split("\n\n", 1)[0]
