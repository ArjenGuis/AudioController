""" Module which handles settings, which are configurable and thus persistent """
import sys
from typing import List
from pathlib import Path
import pickle
from dataclasses import dataclass, field, asdict

from . import fonts

#
# Classes and default settings
#


@dataclass
class Settings:
    """ Settings including field types and default values """
    title: str = "Noorderkerk"
    nr_IN_ports: int = 8  # nr of IN ports on ITEC
    nr_OUT_ports: int = 4  # nr of OUT ports on ITEC
    port_IN_for_streams: str = 'IN4'  # IN port of ITEC, connected to output of this device (raspberry pi) to put audio from stream on
    port_OUT_to_stream: str = ''  # OUT port of ITEC, connected to input of this device (raspberry pi) to forward audio to url
    connect_source_destination: bool = True  # on/off switch: when False, no IN port is routed to OUT port, and streams are disconnected
    show_button_connect: bool = False # to show the button to connect source and destinations. If False, connect_source_destination must be True
    mute_sound: bool = False # on/off switch: when True, all sound is muted by disabling all OUT ports (but keeping streams connected)
    show_button_mute_sound: bool = True # to show the button to mute the sound. If False, mute_sound must be False
    enable_option_auto_switch: bool = False  # to be set by administrator, to enable/disable the option to enable auto scan and switch
    enable_auto_switch: bool = False  # when True, the IN ports belonging to all enabled sources are scanned, and when there is a signal, the source is automatically selected
    timeout_auto_switch: int = 15  # minutes to wait after signal is away, before switching to other
    enable_psalmbord: bool = False  # enable Psalmbord functionaliteit
    enable_logging: bool = True
    version: int = 6  # version of settings, used for upgrades


@dataclass
class Source:
    name: str
    enabled: bool
    port_url: str
    scan_prio: int
    db_level: int
    selected: bool
    id: int = 0


@dataclass
class Destination:
    name: str
    enabled: bool
    port_url_file: str
    selected: bool
    id: int = 0


default_fontfamily = fonts.validate_font_name("Verdana", True)
default_fontsize = fonts.validate_font_size(7, True)
default_fontweight = fonts.validate_font_weight(400, True)


@dataclass
class Psalmbord:
    title: str = ""
    regels: List[dict] = field(default_factory=lambda: [])
    fontfamily: str = default_fontfamily
    fontsize: float = default_fontsize
    fontweight: int = default_fontweight


def psalmbord_as_html() -> str:
    """ Create a html string to display the psalmbord in the browser """
    # title
    if psalmbord.title.strip() != "":
        content = f"<div class='title font_weight {fonts.fonts[psalmbord.fontfamily]}'>{psalmbord.title}</div>\n"
    else:
        content = ""
    
    # regels
    for regel in psalmbord.regels:
        content += f"<div class='regel font_weight {fonts.fonts[psalmbord.fontfamily]}'>"

        col = regel['text'].strip().split(":")
        if len(col) > 1:
            # regel with three columns
            content += "\n\t<span class='col1'>"
            for col1 in col[0].split(" "):
                if col1.strip() != "":
                    content += f"<span>{col1}</span>"
            content += "</span>"

            content += "\n\t<span class='col2'>:</span>"

            content += "\n\t<span class='col3'>"
            for col3 in col[1].split(" "):
                if col3.strip() != "":
                    content += f"<span>{col3}</span>"
            content += "</span>\n"
        else:
            # regel without columns
            """ replace optional ";" with ":" to prevent splitting and alignment """
            content += regel['text'].strip().replace(";",":")
        
        content += "</div>\n"
    return content


def default_sources():
    """ Default sources, used as initial and factory defaults """
    result = [
        Source('Kerkzaal', True, 'IN1', 1, -45, False),
        Source('Trouwzaal', True, 'IN2', 0, -45, False),
        Source('Zaal 3', False, 'IN3', 0, -45, False),
        Source('Microfoon', False, 'IN5', 0, -45, False),
        Source('Noord', False, 'http://meeluisteren.gergemrijssen.nl:8000/noord', 0, -45, False),
        Source('Zuid', True, 'http://meeluisteren.gergemrijssen.nl:8000/zuid', 0, -45, False),
        Source('West', True, 'http://meeluisteren.gergemrijssen.nl:8000/west', 0, -45, False),
        Source('Ref. Omroep 1', False, 'http://ro1.reformatorischeomroep.nl:8003/live', 0, -45, False),
        Source('Ref. Omroep 2', False, 'http://ro2.reformatorischeomroep.nl:8020/live', 0, -45, False),
        Source('Ref. Omroep 3', False, 'http://ro3.reformatorischeomroep.nl:8072/live', 0, -45, False),
    ]
    for i, obj in enumerate(result):
        obj.id = i
    return result


def default_destinations():
    """ Default destinations, used as initial and factory defaults """
    result = [
        Destination('Internet', True, 'OUT1', True),
        Destination('HF scanners', True, 'OUT2', True),
        Destination('Icecast', False, 'icecast://<user>:<pw>@<ip>:<port>/mountpoint', False),
        Destination('Opslaan', False, 'file://', False),
    ]
    for i, obj in enumerate(result):
        obj.id = i
    return result


def default_psalmbord():
    """ Default Psalmbord, used as initial and factory defaults """
    result = Psalmbord()
    result.title = "Liturgie"
    result.regels = [{'text': txt} for txt in [
        "Ps 11 : 1, 3",
        "Ps 22 : 2, 3",
        "Exodus 20 : 1-17",
        "Ps 33 : 1, 2",
        "Ps 44 : 2, 3",
        "Ps 55 : 1, 2",
        "Ps 66 : 2, 3",
        "H.C. Zondag 34",
    ]]
    result.fontfamily = default_fontfamily
    result.fontsize = default_fontsize
    result.fontweight = default_fontweight
    return result


#
# Stores / databases
#

# file to save settings (including sources and destinations)
file = Path.home() / ".audio_controller_settings.pickle"

settings = Settings()
sources: List[Source] = []
destinations: List[Destination] = []
psalmbord = Psalmbord()

#
# Save and load
#


def upgrade(store: dict):
    """ upgrade store, for example after software is updated on a running application/device """
    if not 'version' in store['settings']:
        store['settings']['version'] = 1

    if store['settings']['version'] == 1:
        store['settings']['version'] = 2
        store['settings']['port_OUT_to_stream'] = ''

    if store['settings']['version'] == 2:
        store['settings']['version'] = 3
        store['external_sites'] = []  # [asdict(obj) for obj in default_external_sites()]

    if store['settings']['version'] == 3:
        store['settings']['version'] = 4
        del store['external_sites']

    if store['settings']['version'] == 4:
        store['settings']['version'] = 5
        store['settings']['enable_logging'] = True

    if store['settings']['version'] == 5:
        store['settings']['version'] = 6
        store['settings']['enable_psalmbord'] = False
        store['psalmbord'] = asdict(default_psalmbord())

    if store['settings']['version'] == 6:
        store['settings']['version'] = 7
        store['psalmbord']['fontfamily'] = default_fontfamily
        store['psalmbord']['fontsize'] = default_fontsize
        store['psalmbord']['fontweight'] = default_fontweight

    if store['settings']['version'] == 7:
        store['settings']['version'] = 8
        # use button mute_sound instead of enable/disable streams
        store['settings']["show_button_mute_sound"] = True
        store['settings']["show_button_connect"] = False
        connected = store['settings']['connect_source_destination']
        store['settings']["mute_sound"] = not connected
        store['settings']['connect_source_destination'] = True

    #
    # future upgrades will be placed here
    #


def use_from_store(store: dict):
    """ Clear current settings and update it with values in store. """
    upgrade(store)
    # create / update dataclass objects from store
    settings.__init__(**store['settings'])
    sources.clear()
    destinations.clear()
    for obj in store['sources']: sources.append(Source(**obj))
    for obj in store['destinations']: destinations.append(Destination(**obj))
    psalmbord.__init__(**store['psalmbord'])


def load():
    """ Load settings from file, if available. Return True on success, False otherwise. """
    if file.exists():
        try:
            with open(file, 'rb') as f:
                store: dict = pickle.loads(f.read())
                use_from_store(store)
                save()  # save possible upgrades immediately
                return True
        except:
            return False
    return False


def save():
    """ Save all settings to file """
    with open(file, 'wb') as f:
        store = {
            'settings': asdict(settings),
            'sources': [asdict(obj) for obj in sources],
            'destinations': [asdict(obj) for obj in destinations],
            'psalmbord': asdict(psalmbord),
        }
        f.write(pickle.dumps(store))


def restore():
    """ Restore settings and use all defaults. Save to file """
    store = {
        'settings': asdict(Settings()),
        'sources': [asdict(obj) for obj in default_sources()],
        'destinations': [asdict(obj) for obj in default_destinations()],
        'psalmbord': asdict(default_psalmbord()),
    }
    use_from_store(store)
    save()


def init_settings():
    """ Try to load settings from file. If not possible, restore default settings. """
    if not load():
        restore()


init_settings()


def get_binary():
    """ Get content of settings file as binary object """
    with open(file, 'rb') as f:
        return f.read()


def set_binary(obj):
    """ Set content of settings file from binary object """
    store = pickle.loads(obj)
    if not isinstance(store, dict):
        return
    # check some required attributes (not all, because some appeared after upgrades)
    if not all([field in store for field in 'settings sources destinations'.split()]):
        return
    use_from_store(store)
    with open(file, 'wb') as f:
        f.write(obj)


#
# Validation of values
#


def get_port_nr(port: str, prefix="IN") -> int:
    """ Get number of IN or OUT port, or None if 'port' is not a valid value. """
    # compare with maximum port nr according current settings
    max_nr = settings.nr_IN_ports if prefix == "IN" else settings.nr_OUT_ports
    try:
        assert port.startswith(prefix)
        port_nr = int(port[len(prefix):])
        assert 0 < port_nr <= max_nr
    except:
        return None
    return port_nr


def get_IN_port(port: str) -> int:
    """ Get number of IN port, or None if 'port' is not a valid value. """
    return get_port_nr(port, "IN")


def is_IN_port(port: str):
    """ Return True if port is an IN port. False otherwise. """
    return get_IN_port(port) is not None


def get_OUT_port(port: str) -> int:
    """ Get number of OUT port, or None if 'port' is not a valid value. """
    return get_port_nr(port, "OUT")


def is_OUT_port(port: str):
    """ Return True if port is an OUT port. False otherwise. """
    return get_OUT_port(port) is not None


def is_url(value: str):
    """ Return True if value is an url. False otherwise. """
    return value.startswith("http") or value.startswith("icecast")


def is_file(value: str):
    """ Return True if value is an direction to a file. False otherwise. """
    return value.startswith("file")


def validate_settings(obj: Settings):
    """ Return True if settings are correct, False otherwise. Only check values, not types. Possibly correct values. """
    obj.nr_IN_ports = max(1, min(100, obj.nr_IN_ports))
    obj.nr_OUT_ports = max(1, min(8, obj.nr_OUT_ports))  # cannot be more than 8 (length of byte...)
    if not is_IN_port(obj.port_IN_for_streams):
        # IN port is mandatory, which enables the Pi to send audio to ITEC
        return False
    if not is_OUT_port(obj.port_OUT_to_stream) and not obj.port_OUT_to_stream == "":
        # OUT port is NOT mandatory, but the Pi will not send audio to external url (e.g. icecast) in this case
        return False
    if not obj.show_button_connect and not obj.show_button_mute_sound:
        # cannot disable both buttons
        return False
    # correct underlying values if buttons are hidden
    if not obj.show_button_connect:
        obj.connect_source_destination = True
    if not obj.show_button_mute_sound:
        obj.mute_sound = False
    # turn auto-switch off, if option is disabled
    if obj.enable_auto_switch and not obj.enable_option_auto_switch:
        obj.enable_auto_switch = False
    obj.timeout_auto_switch = max(0, min(60 * 24, obj.timeout_auto_switch))
    return True


assert validate_settings(Settings()), "Default settings are not valid"


def validate_source_attribute(name: str, value):
    """ Validate value for attribute with name of a Source object.
    Return value, or adjusted value, or None if it is not valid. """
    try:
        if name == 'name':
            return value[0:50].strip()  # max 50 characters
        elif name == 'port_url':
            if not (is_IN_port(value) or is_url(value)):
                return None
            else:
                return value.strip()
        elif name == 'scan_prio':
            value = max(0, min(100, value))
        elif name == 'db_level':
            value = max(-70, min(0, value))
        return value
    except:
        return None


def validate_destination_attribute(name: str, value):
    """ Validate value for attribute with name of a Destination object.
    Return value, or adjusted value, or None if it is not valid. """
    try:
        if name == 'name':
            return value[0:50]  # max 50 characters
        elif name == 'port_url_file':  # must be IN port
            if not (is_OUT_port(value) or is_url(value) or is_file(value)):
                return None
        return value
    except:
        return None


def validate_psalmbord(obj: Psalmbord):
    """ Return psalmbord if it is correct, None otherwise. Possibly correct values. """
    try:
        obj.title = obj.title[:100]  # max 100 characters
        if len(obj.regels) > 50:  # max 50 regels
            return None
        default_regel_keys = sorted(list(default_psalmbord().regels[0].keys()))

        for regel in obj.regels:
            if not sorted(list(regel.keys())) == default_regel_keys:
                return None
            regel['text'] = regel['text'][0:100]  # max 100 characters

        obj.fontfamily = str(obj.fontfamily)
        if not fonts.validate_font_name(obj.fontfamily):
            return None
        obj.fontsize = float(obj.fontsize)
        if not fonts.validate_font_size(obj.fontsize):
            return None
        obj.fontweight = int(obj.fontweight)
        if not fonts.validate_font_weight(obj.fontweight):
            return None

        return obj
    except:
        return None


assert validate_psalmbord(default_psalmbord()), "Default psalmbord is not valid"

#
# Updates
#


def update_settings(obj: dict):
    """ Update both cached and saved settings with values from 'obj'. """
    # dictonary with key, value = attribute-name, type
    annot = Settings.__annotations__
    backup = Settings()
    backup.__init__(**asdict(settings))
    for attr in annot.keys():
        if attr in obj:
            try:
                value = annot[attr](obj[attr])  # cast value to type
                setattr(settings, attr, value)
            except:
                pass  # ignore attr
    if validate_settings(settings):
        save()
    else:  # restore
        settings.__init__(**asdict(backup))


def update_sources(new_sources: List[dict]):
    """ Compare sources with current sources, and update the current.
    Each object must contain at least all attributes required to create Source.
    It may contain more, which will be ignored. """
    try:
        # convert all sources to the correct type, let it raise an Exception if its not possible
        fields = Source.__annotations__.copy()
        del fields['id']  # do not copy id
        # create a temporary list, to first validate everything, and then copy
        new_list: List[Source] = []
        for i, obj in enumerate(new_sources):
            new_obj = {}
            # copy attributes
            for attr, value_type in fields.items():
                # cast and validate value
                value = validate_source_attribute(attr, value_type(obj[attr]))
                if value is not None:
                    new_obj[attr] = value
            new_obj = Source(**new_obj)
            new_obj.id = i
            new_list.append(new_obj)
        sources.clear()
        for obj in new_list: sources.append(obj)
        save()
    except:
        pass


def update_destinations(new_destinations: List[dict]):
    """ Compare destinations with current destinations, and update the current.
    Each object must contain at least all attributes required to create Destination.
    It may contain more, which will be ignored. """
    try:
        # convert all sources to the correct type, let it raise an Exception if its not possible
        fields = Destination.__annotations__.copy()
        del fields['id']  # do not copy id
        # create a temporary list, to first validate everything, and then copy
        new_list: List[Destination] = []
        for i, obj in enumerate(new_destinations):
            new_obj = {}
            # copy attributes
            for attr, value_type in fields.items():
                # cast and validate value
                value = validate_destination_attribute(attr, value_type(obj[attr]))
                if value is not None:
                    new_obj[attr] = value
            new_obj = Destination(**new_obj)
            new_obj.id = i
            new_list.append(new_obj)
        destinations.clear()
        for obj in new_list: destinations.append(obj)
        save()
    except:
        pass


def update_psalmbord(title: str, regels: List[dict], fontfamily, fontsize, fontweight):
    temp = Psalmbord(title, regels, fontfamily, fontsize, fontweight)
    temp = validate_psalmbord(temp)
    if temp:
        psalmbord.title = temp.title
        psalmbord.regels = temp.regels
        psalmbord.fontfamily = temp.fontfamily
        psalmbord.fontsize = temp.fontsize
        psalmbord.fontweight = temp.fontweight
        save()


def test():
    return
    sys.exit(0)
