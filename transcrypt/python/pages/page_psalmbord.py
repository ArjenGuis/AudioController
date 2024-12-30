__pragma__('alias', 'S', '$')  # to use jQuery library with 'S' instead of '$'
import utils
from elements import Element, element, ElementWrapper, get_Element, get_elements, get_element
from layout import home, main, set_title
from paged_list import PagedList
from dialogs import dialog_confirm
E = Element

# copied from fonts.py
fonts = ["Arial", "Cambria", "Courier New", "Courier Prime", "Georgia", "Gill Sans", "Verdana"]


def frange(start: float, stop: float, step: float):
    """ range() for floats """
    positive = step > 0
    result = start

    if positive:
        def running(): return (result < stop)
    else:
        def running(): return (result > stop)

    while running():
        yield result
        result += step


# copied from fonts.py
fontsizes = list(range(5, 16))

# copied from fonts.py
fontweights = list(range(300, 900, 100))


def regel(text: str):
    return {"text": text}


class Select(ElementWrapper):
    def __init__(self, name: str, values: dict):
        super().__init__(element('select'))
        self.attr('name', name)
        for v in values:
            self.append(E('option').attr('value', v).inner_html(v))


class Page(ElementWrapper):
    def __init__(self):
        super().__init__(element('div'))
        self.psalmbord: dict = None

        input_title = E('input').attr('class', 'form-control').attr('type', 'text')
        width_1 = 'col-sm-2'
        width_2 = 'col-sm-3'
        self.append(
            E('div').attr('class', 'form-group row').append(
                E('label').attr('class', '{} col-form-label'.format(width_1)).inner_html("Titel"),
                E('div').attr('class', '{}'.format(width_2)).append(input_title)
            ),
        )
        div_list = E('div')
        self.append(div_list)
        plist = PagedList(div_list.element, "").hide_count().disable_pagination()
        plist.get_styling().table_class('table borderless')

        def text_element(attr, item):
            r = E('input').attr('type', 'text').attr('style', 'width: 100%; font-family: monospace;')
            r.element.value = item[attr]

            def onchange(evt):
                item[attr] = r.element.value
                save_changes()
            r.element.onchange = onchange
            return r.element

        plist.add_column('text', 'Tekst').item_to_element(text_element.bind(None, 'text'))

        def set_inputs():
            input_title.element.value = self.psalmbord['title']
            plist.get_server().data = self.psalmbord['regels']
            select_fontfamily.element.value = self.psalmbord['fontfamily']
            select_fontsize.element.value = self.psalmbord['fontsize']
            select_fontweight.element.value = self.psalmbord['fontweight']
            plist.refresh()

        async def delete_item(item):
            self.psalmbord['regels'].remove(item)
            await save_changes()

        async def save_changes():
            self.psalmbord = await utils.post(utils.get_url('general/setPsalmbord'), self.psalmbord)
            set_inputs()

        plist.add_button('delete', '', 'btn btn-danger btn-sm') \
            .use_element(lambda item: E('i').attr("class", 'fas fa-trash-alt')) \
            .onclick(delete_item)

        async def change_order(up: bool, item):
            regels = self.psalmbord['regels']
            i = regels.index(item)
            if not -1 < i < len(regels):
                return
            j = i - 1 if up else i + 1
            j = max(0, min(j, len(regels) - 1))
            regels.remove(item)
            regels.insert(j, item)
            self.psalmbord = await utils.post(utils.get_url('general/setPsalmbord'), self.psalmbord)
            plist.get_server().data = self.psalmbord['regels']
            plist.refresh()

        plist.add_button('up', '', 'btn btn-primary btn-sm') \
            .use_element(lambda item: E('i').attr("class", 'fas fa-sort-up').attr('style', 'font-size: 20px; vertical-align: bottom;')) \
            .onclick(change_order.bind(None, True))

        plist.add_button('down', '', 'btn btn-primary btn-sm') \
            .use_element(lambda item: E('i').attr("class", 'fas fa-sort-down').attr('style', 'font-size: 20px; vertical-align: bottom;')) \
            .onclick(change_order.bind(None, False))

        def add_item(evt):
            self.psalmbord['regels'].append(regel(""))
            plist.get_server().data = self.psalmbord['regels']
            plist.refresh()

        button_add = E('button').attr('class', 'btn btn-primary btn-sm').inner_html("Toevoegen")
        button_add.element.onclick = add_item

        self.append(button_add)

        self.append(E('div').attr('style', 'min-height: 2vh;'))

        select_fontfamily = Select("fontfamily", fonts)
        select_fontsize = Select("fontsize", fontsizes)
        select_fontweight = Select("fontsize", fontweights)

        self.append(
            E('div').attr('class', 'form-group row').append(
                E('label').attr('class', '{} col-form-label'.format(width_1)).inner_html("Letter type"),
                E('div').attr('class', '{}'.format(width_2)).append(select_fontfamily)
            ),
            E('div').attr('class', 'form-group row').append(
                E('label').attr('class', '{} col-form-label'.format(width_1)).inner_html("Aantal regels"),
                E('div').attr('class', '{}'.format(width_2)).append(select_fontsize)
            ),
            E('div').attr('class', 'form-group row').append(
                E('label').attr('class', '{} col-form-label'.format(width_1)).inner_html("Letter dikte"),
                E('div').attr('class', '{}'.format(width_2)).append(select_fontweight)
            ),
        )

        async def initialize():
            self.psalmbord = await utils.post(utils.get_url('general/getPsalmbord'), {})
            set_inputs()

        self.refresh = initialize

        async def onchange(evt):
            self.psalmbord['title'] = input_title.element.value
            self.psalmbord['fontfamily'] = select_fontfamily.element.value
            self.psalmbord['fontsize'] = select_fontsize.element.value
            self.psalmbord['fontweight'] = select_fontweight.element.value
            save_changes()

        input_title.element.onchange = onchange
        select_fontfamily.element.onchange = onchange
        select_fontsize.element.onchange = onchange
        select_fontweight.element.onchange = onchange

    def show(self):
        main.remove_childs()
        main.append(self)
        self.refresh()
