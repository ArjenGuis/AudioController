""" Rules of the users grid on the settings page (issue #23).

Kept free of DOM/browser code on purpose: this module compiles with Transcrypt
AND imports in CPython, so the server test suite exercises exactly the logic the
browser runs (tests/test_users_grid_frontend.py, tests/test_users_grid_flow.py).
pages/page_admin.py only wires it to the input elements.

Two things the grid has to get right:

 - it saves on every single onchange, so it must not post a row that the server
   can only refuse (a half-filled new user);
 - the answer to a save is either the fresh user list (success) or an error
   object. Only the list may become the model; storing the error object made the
   next save post {"users": {"success": false, ...}}.
"""

MSG_NO_USERNAME = "Vul een gebruikersnaam in"
MSG_NO_PASSWORD = "Een nieuwe gebruiker heeft een wachtwoord nodig"
MSG_DUPLICATE = "Deze gebruikersnaam bestaat al"
MSG_FAILED = "Opslaan mislukt"


def new_row():
    """ A blank row for 'Toevoegen'. Empty password: the server rejects the old
    placeholder "password" as weak, and a new user must get a real one. """
    return {"username": "", "password": "", "admin": False, "camera": False}


def is_new(row):
    """ True for a row that the server does not know yet. getUsers hands out an
    orig_username for every stored user; a row added here has none. """
    return not field(row, "orig_username")


def field(row, name):
    """ Read one field of a row. Rows come straight from JSON.parse, so they are
    plain objects without Transcrypt's dict methods: .get() would throw in the
    browser. Indexing works in both worlds (JS yields undefined, CPython
    raises). """
    try:
        return row[name]
    except Exception:
        return None


def validate(rows):
    """ Return "" when this list may be posted, else the reason (shown to the
    admin instead of firing a save that can only fail). """
    names = []
    for row in rows:
        username = str(field(row, "username") or "").strip()
        if not username:
            return MSG_NO_USERNAME
        # A rename keeps the stored password (the server matches the record by
        # orig_username), so only a genuinely new row needs one.
        if is_new(row) and not field(row, "password"):
            return MSG_NO_PASSWORD
        # login is case-insensitive, so "Beheer" and "beheer" are one account
        if username.lower() in names:
            return MSG_DUPLICATE
        names.append(username.lower())
    return ""


def apply_result(rows, result):
    """ Feed the answer of setUsers back into the grid: return (rows, error).

    On success the server answers with the fresh user list and that becomes the
    model. Anything else is an error: keep the rows the admin is editing, so a
    mistake can be corrected instead of wrecking the grid. """
    if _is_user_list(result):
        return result, ""
    return rows, _error_text(result)


def _is_user_list(result):
    """ True if `result` is the user list. Duck-typed on append(), which holds
    for a CPython list and for a JS Array under Transcrypt, unlike the parsed
    error object in either. """
    return result is not None and hasattr(result, "append")


def _error_text(result):
    message = field(result, "error")
    if not message:
        return MSG_FAILED
    return str(message)
