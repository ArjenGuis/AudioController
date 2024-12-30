""" Functions to handle fonts in settings.py """

# ON CHANGE, ALSO CHANGE page_psalmbord.py (client side code)
fonts = {  # key: name, value: css style class
    "Arial": "font_arial",
    "Cambria": "font_cambria",
    "Courier New": "font_courier_new",
    "Courier Prime": "font_courier_prime",
    "Georgia": "font_georgia",
    "Gill Sans": "font_gill_sans",
    "Verdana": "font_verdana",
}


def frange(start: float, stop: float, step: float):
    """ range() for floats """
    if step == 0:
        raise Exception("step cannot be zero")
    positive = step > 0
    result = start

    if positive:
        def running(): return (result < stop)
    else:
        def running(): return (result > stop)

    while running():
        yield result
        result += step


# ON CHANGE, ALSO CHANGE page_psalmbord.py (client side code)
fontsizes = list(range(5, 16))
fontweights = list(range(300, 900, 100))

def validate_font_name(font_name: str, raise_exc=False):
    if font_name in fonts:
        return font_name
    if raise_exc:
        raise Exception(f"Invalid font_name {font_name}")
    return None


def validate_font_size(font_size: float, raise_exc=False):
    if font_size in fontsizes:
        return font_size
    if raise_exc:
        raise Exception(f"Invalid font_size {font_size}")
    return None


def validate_font_weight(font_weight: int, raise_exc=False):
    if font_weight in fontweights:
        return font_weight
    if raise_exc:
        raise Exception(f"Invalid font_weight {font_weight}")
    return None


# print(styles_to_css())
#import sys
# sys.exit(0)
