"""Unit tests for the users grid save path (issue #23).

The admin grid never prefills the password field, so every save posts a BLANK
password for an unchanged user. update_users therefore matched the stored record
by username -- which made a RENAME impossible: the new name matched nothing, and
the save was refused with "een nieuwe of hernoemde gebruiker vereist een
wachtwoord". Renaming and changing a password can never happen in one post: the
grid saves on every individual onchange.

The fix: the server hands out an `orig_username` with every row (getUsers) and
the client posts it back, so a renamed row is still matched to its stored record
by identity instead of by name.
"""
import pytest

from audio_controller import settings, user


def test_rename_with_orig_username_keeps_the_password(tmp_settings_file):
    # issue #23, testcase 2: renaming 'koster' -> 'kostert' with a blank password
    # must succeed and keep the stored password.
    settings.update_users([{"username": "koster", "password": "Sterk!wachtwoord9",
                            "admin": False, "camera": True}])
    settings.update_users([{"username": "kostert", "orig_username": "koster",
                            "password": "", "admin": False, "camera": True}])

    assert [u.username for u in settings.users] == ["kostert"]
    assert user.verify_password("Sterk!wachtwoord9", settings.users[0].password)
    assert settings.users[0].camera is True


def test_rename_keeps_must_change_password_flag(tmp_settings_file):
    # a forced-change account that is renamed stays forced; renaming must not
    # silently clear the gate.
    settings.restore()                      # default admin, must_change_password
    assert settings.users[0].must_change_password is True
    settings.update_users([{"username": "beheerder", "orig_username": "admin",
                            "password": "", "admin": True, "camera": True}])
    assert settings.users[0].username == "beheerder"
    assert settings.users[0].must_change_password is True


def test_rename_and_new_password_in_one_save(tmp_settings_file):
    settings.update_users([{"username": "koster", "password": "Sterk!wachtwoord9",
                            "admin": False}])
    settings.update_users([{"username": "kostert", "orig_username": "koster",
                            "password": "Nog!sterker8", "admin": False}])
    assert settings.users[0].username == "kostert"
    assert user.verify_password("Nog!sterker8", settings.users[0].password)


def test_unknown_orig_username_is_treated_as_a_new_user(tmp_settings_file):
    # a stale client (or a hand-made post) naming a record that no longer exists
    # must not store an empty password: it is a new user and needs one.
    settings.update_users([{"username": "koster", "password": "Sterk!wachtwoord9"}])
    with pytest.raises(ValueError):
        settings.update_users([{"username": "koster", "password": "Sterk!wachtwoord9"},
                               {"username": "nieuw", "orig_username": "bestaatniet",
                                "password": ""}])
    assert [u.username for u in settings.users] == ["koster"]


def test_two_rows_cannot_claim_the_same_stored_record(tmp_settings_file):
    # copying one account's stored hash onto a second row would hand that user's
    # password to another account; refuse instead of cloning it.
    settings.update_users([{"username": "koster", "password": "Sterk!wachtwoord9"}])
    with pytest.raises(ValueError):
        settings.update_users([{"username": "koster", "orig_username": "koster",
                                "password": ""},
                               {"username": "kopie", "orig_username": "koster",
                                "password": ""}])
    assert [u.username for u in settings.users] == ["koster"]


def test_blank_password_without_orig_username_still_keeps_by_name(tmp_settings_file):
    # unchanged rows (checkbox toggle) keep working when the client sends no
    # orig_username at all -- e.g. an older cached main.js.
    settings.update_users([{"username": "beheer", "password": "Sterk!wachtwoord9",
                            "admin": False, "camera": True}])
    settings.update_users([{"username": "beheer", "password": "", "admin": True,
                            "camera": True}])
    assert settings.users[0].admin is True
    assert user.verify_password("Sterk!wachtwoord9", settings.users[0].password)


def test_orig_username_is_not_stored_on_the_user_record(tmp_settings_file):
    # it is wire-only routing information, never persisted
    settings.update_users([{"username": "koster", "orig_username": "koster",
                            "password": "Sterk!wachtwoord9"}])
    assert not hasattr(settings.users[0], "orig_username")
    assert "orig_username" not in settings.file.read_text(encoding="utf-8")
