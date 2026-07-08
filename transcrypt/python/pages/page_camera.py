import utils
from elements import Element, element, ElementWrapper, get_Element, get_elements, get_element
from layout import home, main, set_title
E = Element

class Page(ElementWrapper):

    def __init__(self):
        super().__init__(element('div'))
        self.attr('style', 'max-width: 1000px;')

    def show(self):
        main.remove_childs()
        main.append(self)
        self.refresh()

