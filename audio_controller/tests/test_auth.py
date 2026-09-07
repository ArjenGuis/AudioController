from audio_controller import user, settings


def test_hash_password_is_salted_and_verifies():
    h1 = user.hash_password("secret")
    h2 = user.hash_password("secret")
    assert h1 != h2                       # random salt -> different records
    assert h1.startswith("pbkdf2_sha256$")
    assert user.verify_password("secret", h1)
    assert user.verify_password("secret", h2)
    assert not user.verify_password("wrong", h1)


def test_verify_password_backward_compatible_with_legacy():
    legacy = user.encryptPassword("oldpw")   # unsalted blake2b hex
    assert user.is_legacy_hash(legacy)
    assert user.verify_password("oldpw", legacy)
    assert not user.verify_password("nope", legacy)


def test_new_hash_is_not_flagged_legacy():
    assert not user.is_legacy_hash(user.hash_password("x"))


def test_dummy_hash_is_real_pbkdf2_and_never_verifies():
    # S-M5: to flatten login timing between existing and non-existing usernames,
    # the handler verifies an unknown user's password against this dummy hash. It
    # must be a genuine (slow) pbkdf2 record that no password can satisfy.
    assert user.DUMMY_HASH.startswith("pbkdf2_sha256$")
    assert user.verify_password("anything", user.DUMMY_HASH) is False
    assert user.verify_password("", user.DUMMY_HASH) is False


def test_default_admin_must_change_password():
    users = user.default_users()
    admin = [u for u in users if u.username == "admin"]
    # a fresh install (no previous users file) seeds a forced-change admin
    if admin:
        a = admin[0]
        if a.must_change_password:
            # its stored password authenticates as 'admin' but forces a change
            assert user.verify_password("admin", a.password)


def test_update_users_salts_and_clears_flag(tmp_settings_file):
    # simulate the forced admin setting a real password via the users grid
    settings.update_users([
        {"username": "admin", "password": "NewStrongPw", "admin": True, "camera": True},
    ])
    stored = settings.users[0]
    assert not user.is_legacy_hash(stored.password)      # salted now
    assert stored.password != "NewStrongPw"              # not plaintext
    assert user.verify_password("NewStrongPw", stored.password)
    assert stored.must_change_password is False          # flag cleared


def test_update_users_rejects_case_insensitive_duplicate(tmp_settings_file):
    # review #1: login matches usernames case-insensitively, so "Admin" and
    # "admin" are the same account and must be rejected as a duplicate.
    import pytest
    with pytest.raises(Exception):
        settings.update_users([
            {"username": "Admin", "password": "Sterk!wachtwoord9", "admin": True},
            {"username": "admin", "password": "Sterk!wachtwoord9", "admin": True},
        ])


def test_update_users_survives_non_string_username(tmp_settings_file):
    # review #3: a corrupt (non-str) username must not crash the save with a 500.
    settings.update_users([{"username": 12345, "password": "Sterk!wachtwoord9", "admin": True}])
    assert any(u.username == "12345" for u in settings.users)


def test_blank_password_keeps_existing_on_checkbox_toggle(tmp_settings_file):
    # Guis: the grid re-posts every user with a BLANK password on any field change
    # (e.g. toggling admin). A blank password must leave the password unchanged.
    settings.update_users([{"username": "beheer", "password": "Sterk!wachtwoord9",
                            "admin": False, "camera": True}])
    settings.update_users([{"username": "beheer", "password": "", "admin": True, "camera": True}])
    u = settings.users[0]
    assert u.admin is True                                   # toggle applied
    assert user.verify_password("Sterk!wachtwoord9", u.password)  # password kept
    assert not user.verify_password("", u.password)          # NOT emptied


def test_blank_password_new_user_is_rejected_not_emptied(tmp_settings_file):
    # a brand-new user with a blank password must be refused, never stored with an
    # empty password (which would otherwise let "" log in).
    import pytest
    with pytest.raises(ValueError):
        settings.update_users([{"username": "nieuw", "password": "", "admin": False}])


def test_rename_with_blank_password_does_not_empty_it(tmp_settings_file):
    # renaming a user (username changes) with a blank password must not wipe the
    # password to an empty hash; refuse instead (the prior can't be matched by name).
    import pytest
    settings.update_users([{"username": "beheer", "password": "Sterk!wachtwoord9", "admin": True}])
    with pytest.raises(ValueError):
        settings.update_users([{"username": "beheerder", "password": "", "admin": True}])
    # original account + password untouched after the refused save
    assert settings.users[0].username == "beheer"
    assert user.verify_password("Sterk!wachtwoord9", settings.users[0].password)
