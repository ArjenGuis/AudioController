"""End-to-end replay of the users grid (issue #23).

Drives the real handlers over HTTP the way the SPA's Gebruikers grid does, with
the grid's own logic (transcrypt/python/users_grid.py) as the client: load the
whole list, change ONE field, post the whole list back, feed the answer into the
model. That combination is what broke -- each half looked fine on its own.

The testcases mirror the ones in the issue.
"""
import importlib.util
import json
import re
from pathlib import Path

from tornado.testing import AsyncHTTPTestCase

from audio_controller import __main__ as appmod
from audio_controller import settings, user

_GRID_MODULE = (Path(__file__).resolve().parents[2] / "transcrypt" / "python"
                / "users_grid.py")


def _load_grid_logic():
    spec = importlib.util.spec_from_file_location("users_grid", _GRID_MODULE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


users_grid = _load_grid_logic()


class _GridFlow(AsyncHTTPTestCase):
    """The loopback listener: the local operator UI manages users without login."""

    def get_app(self):
        return appmod.make_app(internal=True)

    def setUp(self):
        super().setUp()
        settings.restore()
        settings.update_users([
            {"username": "beheer", "password": "Sterk!wachtwoord9",
             "admin": True, "camera": True},
            {"username": "koster", "password": "Koster!wachtwoord9",
             "admin": False, "camera": True},
        ])
        r = self.fetch("/", method="GET")
        m = re.search(r"_xsrf=([^;]+)", "; ".join(r.headers.get_list("Set-Cookie")))
        self.xsrf = m.group(1)
        # the grid's model, exactly like the SPA holds it
        self.rows = []
        self.error = ""

    # -- the SPA's two XHR calls -------------------------------------------

    def _post(self, path, body, referer=None):
        headers = {
            "Content-Type": "application/json",
            "X-Xsrftoken": self.xsrf,
            "Cookie": f"_xsrf={self.xsrf}",
        }
        if referer:
            headers["Referer"] = referer
        r = self.fetch(path, method="POST", body=json.dumps(body), headers=headers)
        self.assertEqual(r.code, 200)
        return json.loads(r.body)

    def load_grid(self):
        """initialize(): getUsers -> the grid's model"""
        self.rows = self._post("/login/getUsers", {})
        return self.rows

    def save_grid(self):
        """save_changes(): post wat verstuurd mag worden, en verwerk het antwoord"""
        rows, message = users_grid.prepare_save(self.rows)
        if rows is None:
            self.error = message
            return None
        leftover = users_grid.unsaved_rows(self.rows, rows)
        result = self._post("/login/setUsers", {"users": rows})
        applied, error = users_grid.apply_result(self.rows, result)
        self.rows = applied if error else applied + leftover
        self.error = error or message
        return result

    def edit(self, index, attr, value):
        """one onchange in the grid: set the field, then save"""
        self.rows[index][attr] = value
        return self.save_grid()

    def login(self, username, password):
        # from the camera app: a non-admin may only log in there (check_app)
        return self._post("/login/login", {"username": username,
                                           "password": password},
                          referer="http://127.0.0.1/camera")


class TestUsersGridFlow(_GridFlow):

    # -- testcase 1: a new user -------------------------------------------

    def test_adding_a_user_needs_a_username_and_a_password(self):
        self.load_grid()
        self.rows.append(users_grid.new_row())
        # typing only the username must not fire a doomed save
        self.edit(2, "username", "pietjepuk")
        self.assertNotEqual(self.error, "")
        self.assertEqual(len(self.load_grid()), 2)   # nothing stored yet

    def test_adding_a_user_succeeds_once_the_password_is_filled_in(self):
        self.load_grid()
        self.rows.append(users_grid.new_row())
        self.edit(2, "username", "pietjepuk")
        self.rows[2]["camera"] = True
        self.edit(2, "password", "ditiseenmoeilijkwachtwoord")

        self.assertEqual(self.error, "")
        self.assertEqual([r["username"] for r in self.rows],
                         ["beheer", "koster", "pietjepuk"])
        self.assertTrue(self.login("pietjepuk", "ditiseenmoeilijkwachtwoord")["success"])

    def test_a_weak_password_is_reported_and_does_not_corrupt_the_model(self):
        # the cascade in the issue: the error object became the model, so the
        # next save posted {"users": {"success": false, ...}}.
        self.load_grid()
        self.rows.append(users_grid.new_row())
        self.rows[2]["username"] = "pietjepuk"
        self.rows[2]["camera"] = True
        self.edit(2, "password", "password")
        self.assertEqual(self.error, "Kies een sterker wachtwoord")
        self.assertIsInstance(self.rows, list)

        # recovering by typing a real password just works
        self.edit(2, "password", "ditiseenmoeilijkwachtwoord")
        self.assertEqual(self.error, "")
        self.assertTrue(self.login("pietjepuk", "ditiseenmoeilijkwachtwoord")["success"])

    # -- testcase 2: renaming ---------------------------------------------

    def test_renaming_a_user_keeps_the_password(self):
        self.load_grid()
        self.edit(1, "username", "kostert")

        self.assertEqual(self.error, "")
        self.assertEqual([r["username"] for r in self.rows], ["beheer", "kostert"])
        self.assertTrue(self.login("kostert", "Koster!wachtwoord9")["success"])
        self.assertFalse(self.login("koster", "Koster!wachtwoord9")["success"])

    def test_renaming_twice_in_a_row_works(self):
        # the second rename must match the record by its NEW name, i.e. the grid
        # has to refresh orig_username from the save's answer.
        self.load_grid()
        self.edit(1, "username", "kostert")
        self.edit(1, "username", "kosterix")
        self.assertEqual(self.error, "")
        self.assertTrue(self.login("kosterix", "Koster!wachtwoord9")["success"])

    def test_renaming_onto_an_existing_name_is_refused(self):
        self.load_grid()
        self.edit(1, "username", "beheer")
        self.assertNotEqual(self.error, "")
        # the stored accounts are untouched
        self.assertEqual([u.username for u in settings.users], ["beheer", "koster"])

    # -- testcases 3/4/5: password and the checkboxes ----------------------

    def test_changing_only_the_password_works(self):
        self.load_grid()
        self.edit(1, "password", "moeilijkwachtwoord")
        self.assertEqual(self.error, "")
        self.assertTrue(self.login("koster", "moeilijkwachtwoord")["success"])

    def test_toggling_a_checkbox_keeps_the_password(self):
        self.load_grid()
        self.edit(1, "admin", True)
        self.assertEqual(self.error, "")
        self.assertTrue(settings.users[1].admin)
        self.assertTrue(self.login("koster", "Koster!wachtwoord9")["success"])

    def test_revoking_the_camera_right_takes_effect(self):
        # issue #23 testcase 5
        self.load_grid()
        self.edit(1, "camera", False)
        self.assertEqual(self.error, "")
        self.assertFalse(self.login("koster", "Koster!wachtwoord9")["success"])

    # -- the wire contract the grid depends on ----------------------------

    def test_getusers_hands_out_an_orig_username_per_row(self):
        rows = self.load_grid()
        self.assertEqual([r["orig_username"] for r in rows], ["beheer", "koster"])
        self.assertTrue(all(r["password"] == "" for r in rows))   # never the hash

    def test_a_successful_save_answers_with_the_fresh_list(self):
        # the grid replaces its model with this answer, so it must be the list
        # (a dict would end up as the next request's payload).
        self.load_grid()
        result = self.edit(1, "camera", True)
        self.assertIsInstance(result, list)
        self.assertEqual([r["orig_username"] for r in result], ["beheer", "koster"])

    def test_a_refused_save_answers_with_an_error_message(self):
        self.load_grid()
        self.rows[1]["password"] = "admin"          # weak
        result = self._post("/login/setUsers", {"users": self.rows})
        self.assertFalse(result["success"])
        self.assertTrue(result["error"])


class TestStrayRowDoesNotBlockTheGrid(_GridFlow):

    def test_an_unfinished_new_row_does_not_block_another_change(self):
        # "Toevoegen" aangeklikt en niets ingevuld; daarna het camera-vinkje van
        # een bestaande gebruiker omzetten. Dat moet gewoon opgeslagen worden.
        self.load_grid()
        self.rows.append(users_grid.new_row())
        self.edit(1, "admin", True)

        self.assertTrue(settings.users[1].admin)          # wel opgeslagen
        self.assertNotEqual(self.error, "")               # met een melding erover
        self.assertEqual(len(self.rows), 3)               # de lege rij staat er nog
        self.assertEqual([u.username for u in settings.users], ["beheer", "koster"])

    def test_the_stray_row_is_saved_as_soon_as_it_is_complete(self):
        self.load_grid()
        self.rows.append(users_grid.new_row())
        self.edit(1, "admin", True)
        self.rows[2]["username"] = "pietjepuk"
        self.edit(2, "password", "ditiseenmoeilijkwachtwoord")

        self.assertEqual(self.error, "")
        self.assertEqual([u.username for u in settings.users],
                         ["beheer", "koster", "pietjepuk"])


class TestSelfRenameKeepsTheSession(AsyncHTTPTestCase):
    """De externe poort, waar wel ingelogd moet worden.

    setUser (het wijzigformulier in de camera-app) herstelt de cookie na een
    zelf-hernoeming; setUsers deed dat niet. Dat viel niet op zolang hernoemen
    in de grid onmogelijk was -- nu wel: de cookie houdt de oude naam vast,
    get_user() vindt die niet meer, en elke admin-actie antwoordt daarna met
    "Geen rechten" zonder enige uitleg.
    """

    def get_app(self):
        return appmod.make_app(internal=False)

    def setUp(self):
        super().setUp()
        settings.restore()
        settings.update_users([
            {"username": "beheer", "password": "Sterk!wachtwoord9",
             "admin": True, "camera": True},
        ])
        r = self.fetch("/", method="GET")
        m = re.search(r"_xsrf=([^;]+)", "; ".join(r.headers.get_list("Set-Cookie")))
        self.xsrf = m.group(1)
        self.cookie = f"_xsrf={self.xsrf}"
        login = self._post("/login/login", {"username": "beheer",
                                            "password": "Sterk!wachtwoord9"})
        assert login["success"], login
        self._remember_cookies(self._last_headers)

    def _remember_cookies(self, headers):
        for c in headers.get_list("Set-Cookie"):
            name_value = c.split(";")[0]
            name = name_value.split("=")[0]
            parts = [p for p in self.cookie.split("; ") if not p.startswith(name + "=")]
            self.cookie = "; ".join(parts + [name_value])

    def _post(self, path, body):
        r = self.fetch(path, method="POST", body=json.dumps(body), headers={
            "Content-Type": "application/json",
            "X-Xsrftoken": self.xsrf,
            "Cookie": self.cookie,
        })
        self.assertEqual(r.code, 200)
        self._last_headers = r.headers
        return json.loads(r.body)

    def test_renaming_yourself_keeps_you_logged_in(self):
        rows = self._post("/login/getUsers", {})
        rows[0]["username"] = "beheerder"
        result = self._post("/login/setUsers", {"users": rows})
        self.assertIsInstance(result, list)
        self._remember_cookies(self._last_headers)      # de app stuurt de nieuwe naam mee

        # de sessie is nog geldig: getUsers is admin-only
        again = self._post("/login/getUsers", {})
        self.assertIsInstance(again, list)
        self.assertEqual([r["username"] for r in again], ["beheerder"])

    def test_renaming_someone_else_leaves_your_own_cookie_alone(self):
        settings.update_users([
            {"username": "beheer", "password": "Sterk!wachtwoord9", "admin": True},
            {"username": "koster", "password": "Koster!wachtwoord9", "camera": True},
        ])
        rows = self._post("/login/getUsers", {})
        rows[1]["username"] = "kostert"
        self._post("/login/setUsers", {"users": rows})
        self._remember_cookies(self._last_headers)
        again = self._post("/login/getUsers", {})
        self.assertEqual([r["username"] for r in again], ["beheer", "kostert"])
