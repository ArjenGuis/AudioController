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
MSG_NEW_INCOMPLETE = "De nieuwe gebruiker is nog niet opgeslagen: vul een gebruikersnaam en een wachtwoord in"
MSG_DUPLICATE = "Deze gebruikersnaam bestaat al"
MSG_FAILED = "Opslaan mislukt"
MSG_CHANGE_PASSWORD = "Wijzig eerst uw eigen wachtwoord"


def new_row():
    """ A blank row for 'Toevoegen'. Empty password: the server rejects the old
    placeholder "password" as weak, and a new user must get a real one. """
    return {"username": "", "password": "", "admin": False, "camera": False}


def is_new(row):
    """ True for a row that the server does not know yet. getUsers hands out an
    orig_username for every stored user; a row added here has none. """
    return not field(row, "orig_username")


def is_missing(value):
    """ True voor None, en in de browser ook voor undefined.

    Transcrypt vertaalt '== None' naar '== null' (losse gelijkheid), en dat vangt
    undefined mee; 'is None' wordt '=== null' en zou eroverheen lopen. In CPython
    betekent het gewoon None. """
    return value == None  # noqa: E711 -- bewust geen 'is None', zie hierboven


def field(row, name):
    """ Read one field of a row. Rows come straight from JSON.parse, so they are
    plain objects without Transcrypt's dict methods: .get() would throw in the
    browser. Indexing works in both worlds (JS yields undefined, CPython
    raises) -- maar indexeren op null/undefined gooit in JS een TypeError die
    Transcrypt's except niet vangt, dus die vangen we hier af. """
    if is_missing(row):
        return None
    try:
        return row[name]
    except Exception:
        return None


def prepare_save(rows):
    """ Bepaal wat er verstuurd mag worden: (rijen, melding).

    De rijen zijn None als er niets verstuurd mag worden.

    "Toevoegen" zet een lege rij neer en de grid heeft geen verwijderknop, dus
    een half ingevulde nieuwe rij mag de rest niet gijzelen: die gaat niet mee
    tot hij af is, met een melding erbij. Een BESTAANDE rij zonder naam houdt de
    opslag wel tegen -- weglaten zou dat account wissen en zo opslaan geeft een
    account zonder naam, waar get_user("") op matcht.

    En nooit een lege lijst: de server vervangt de hele gebruikerslijst, dus dat
    zou elk account wissen. """
    posted = []
    names = []
    message = ""

    for row in rows:
        username = str(field(row, "username") or "").strip()
        if is_new(row):
            # een rename houdt het opgeslagen wachtwoord (de server zoekt het
            # record op orig_username), dus alleen een echt nieuwe rij heeft er een nodig
            if not username or not field(row, "password"):
                message = MSG_NEW_INCOMPLETE
                continue
        elif not username:
            return None, MSG_NO_USERNAME
        # login is hoofdletter-ongevoelig, dus "Beheer" en "beheer" zijn er een
        if username.lower() in names:
            return None, MSG_DUPLICATE
        names.append(username.lower())
        posted.append(row)

    # len(...) == 0 en niet 'not posted': Transcrypt vertaalt dat naar !posted, en
    # een lege array is in JavaScript waar. De bewaking zou in de browser dus
    # nooit vuren -- precies het geval dat elk account zou wissen.
    if len(posted) == 0:
        return None, message or MSG_NO_USERNAME
    return posted, message


def unsaved_rows(rows, posted):
    """ De rijen die niet mee konden: nieuw en nog niet af.

    Na een geslaagde opslag komt er een verse lijst van de server terug, en die
    kent zo'n rij niet. Zonder deze rijen erbij te houden verdwijnt onder de
    handen van de beheerder wat hij net aan het invullen was. """
    if is_missing(posted):
        return []
    return [row for row in rows if is_new(row) and row not in posted]


def keep_unsaved(saved, leftover):
    """ Zet de nog niet opgeslagen rijen achter de verse lijst van de server.

    Bewust met append in plaats van 'saved + leftover': Transcrypt vertaalt de
    plus naar de JavaScript-plus, en die plakt twee arrays aan elkaar tot een
    string. In CPython zou het wel werken, dus de testsuite ziet het verschil
    niet -- in de browser verdween de grid. """
    result = []
    for row in saved:
        result.append(row)
    for row in leftover:
        result.append(row)
    return result


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
    if is_missing(result):
        return False
    return hasattr(result, "append")


def _error_text(result):
    message = field(result, "error")
    if not message and field(result, "must_change_password"):
        # dit antwoord heeft geen 'error'; zonder eigen tekst zou de beheerder
        # moeten raden waarom er niets wordt opgeslagen
        return MSG_CHANGE_PASSWORD
    if not message:
        return MSG_FAILED
    return str(message)
