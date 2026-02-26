__pragma__('alias', 'S', '$')  # to use jQuery library with 'S' instead of '$'
import utils
from elements import Element, element, ElementWrapper, get_Element, get_elements, get_element
from layout import home, main, set_title
from paged_list import PagedList
from dialogs import dialog_confirm
E = Element

# copied from fonts.py
fonts = ["Arial", "Cambria", "Courier New", "Courier Prime", "Georgia", "Gill Sans", "Verdana", "Samsung"]


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

        width_1 = 'col-sm-1'
        width_2 = 'col-sm-2'
        width_3 = 'col-sm-3'

        # col_1 = left column with config forms
        col_1 = E('div').attr('style', 'float: left; width: 75%')

        # config item: titel regel
        input_title = E('input').attr('class', 'form-control').attr('type', 'text')
        col_1.append(
            E('div').attr('class', 'form-group row').append(
                E('label').attr('class', '{} col-form-label'.format(width_2)).inner_html("Titel"),
                E('div').attr('class', '{}'.format(width_3)).append(input_title)
            ),
        )

        #config item: tekst regels
        def text_element(attr, item):
            r = E('input').attr('type', 'text').attr('style', 'width: 100%; font-family: monospace;')
            r.element.value = item[attr]

            def onchange(evt):
                item[attr] = r.element.value
                save_changes()
            r.element.onchange = onchange
            return r.element

        def set_inputs():
            input_title.element.value = self.psalmbord['title']
            plist_regels.get_server().data = self.psalmbord['regels']
            select_fontfamily.element.value = self.psalmbord['fontfamily']
            select_fontsize.element.value = self.psalmbord['fontsize']
            select_fontweight.element.value = self.psalmbord['fontweight']
            select_screens[self.psalmbord['active']].element.checked = True
            plist_regels.refresh()

        def regel(text: str):
            return {"text": text}

        def add_regel(evt):
            self.psalmbord['regels'].append(regel(""))
            plist_regels.get_server().data = self.psalmbord['regels']
            plist_regels.refresh()

        async def delete_regel(item):
            self.psalmbord['regels'].remove(item)
            await save_changes()

        async def save_changes():
            self.psalmbord = await utils.post(utils.get_url('general/setPsalmbord'), self.psalmbord)
            set_inputs()

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
            plist_regels.get_server().data = self.psalmbord['regels']
            plist_regels.refresh()

        div_list = E('div')
        col_1.append(div_list)
        plist_regels = PagedList(div_list.element, "").hide_count().disable_pagination()
        plist_regels.get_styling().table_class('table borderless')

        plist_regels.add_column('text', 'Regels').item_to_element(text_element.bind(None, 'text'))

        plist_regels.add_button('delete', '', 'btn btn-danger btn-sm') \
            .use_element(lambda item: E('i').attr("class", 'fas fa-trash-alt')) \
            .onclick(delete_regel)

        plist_regels.add_button('up', '', 'btn btn-primary btn-sm') \
            .use_element(lambda item: E('i').attr("class", 'fas fa-sort-up').attr('style', 'font-size: 20px; vertical-align: bottom;')) \
            .onclick(change_order.bind(None, True))

        plist_regels.add_button('down', '', 'btn btn-primary btn-sm') \
            .use_element(lambda item: E('i').attr("class", 'fas fa-sort-down').attr('style', 'font-size: 20px; vertical-align: bottom;')) \
            .onclick(change_order.bind(None, False))

        # tekst regel toevoegen
        button_add_regel = E('button').attr('class', 'btn btn-primary btn-sm').inner_html("Regel toevoegen")
        button_add_regel.element.onclick = add_regel

        col_1.append(button_add_regel)

        # custom screens
        select_screens = []
        select_screens.append( 
            E("input").attr("class", "form-control").attr('id','screen0').attr("type", "radio").attr('name','active').attr('value','0')
        )
        select_screens.append(
            E("input").attr("class", "form-control").attr('id','screen1').attr("type", "radio").attr('name','active').attr('value','1')
        )

        screens_div = E('div').attr('class','row')
        i = 0
        for s in select_screens:
            id = f'screen{i}'
            if i == 0:
                label = "Leeg"
            elif i == 1:
                label = "Met regels"
            else:
                label = "Met tekst"

            screens_div.append(
                E('div').attr('class','{} screen'.format(width_2)).append(
                    s,
                    E('label').attr('class','col-form-label').attr('for',id).inner_html( label )
                )
            )
            i = i+1

        col_1.append( 
            E('p').attr('class','psalmbord_heading').inner_html('Schermen'),
            screens_div
        )

        # add screen
        def add_screen(evt):
            i = select_screens.length
            id = f'screen{i}'
            
            s = E("input").attr("class", "form-control").attr('id',id).attr("type", "radio").attr('name','active').attr('value',i)
            d = E('button').attr('class','btn btn-danger btn-sm').attr('style','float:right; margin: 5px 0;').append( E('i').attr("class", 'fas fa-trash-alt') )
            d.element.onclick = delete_screen

            select_screens.append( s )

            screens_div.append(
                E('div').attr('class','{} screen'.format(width_2)).attr('data-id',i).append(
                    s,
                    E('label').attr('class','col-form-label').attr('for',id).inner_html( 'Met tekst' ),
                    d,
                    E('textarea').attr('name',id),
                )
            )

            s.element.onchange = onchange

        def delete_screen(evt):
            div = evt.target.closest(".screen")
            id = div.dataset.id

            del select_screens[id]
            div.remove()

        button_add_screen = E('button').attr('class', 'btn btn-primary btn-sm').inner_html("Scherm toevoegen")
        button_add_screen.element.onclick = add_screen

        col_1.append(button_add_screen)

        # spacer
        col_1.append( E('p').attr('class','psalmbord_heading').inner_html('Instellingen') )

        # config settings
        select_fontfamily = Select("fontfamily", fonts)
        select_fontsize = Select("fontsize", fontsizes)
        select_fontweight = Select("fontsize", fontweights)

        col_1.append(
            E('div').attr('class', 'form-group row').append(
                E('label').attr('class', '{} col-form-label'.format(width_2)).inner_html("Aantal regels"),
                E('div').attr('class', '{}'.format(width_3)).append(select_fontsize)
            ),
            E('div').attr('class', 'form-group row').append(
                E('label').attr('class', '{} col-form-label'.format(width_2)).inner_html("Lettertype"),
                E('div').attr('class', '{}'.format(width_3)).append(select_fontfamily)
            ),
            E('div').attr('class', 'form-group row').append(
                E('label').attr('class', '{} col-form-label'.format(width_2)).inner_html("Letterdikte"),
                E('div').attr('class', '{}'.format(width_3)).append(select_fontweight)
            ),
        )
        self.append(col_1)

        # col_2 = right column with output frame
        col_2 = E('div').attr('style', 'float: left; width: 25%').append(
            E('iframe').attr('src', '/psalmbord').attr('style', 'width: 360px; height: 640px;')
        )
        self.append(col_2)

        async def initialize():
            self.psalmbord = await utils.post(utils.get_url('general/getPsalmbord'), {})
            set_inputs()

        self.refresh = initialize

        async def onchange(evt):
            self.psalmbord['title'] = input_title.element.value
            self.psalmbord['fontfamily'] = select_fontfamily.element.value
            self.psalmbord['fontsize'] = select_fontsize.element.value
            self.psalmbord['fontweight'] = select_fontweight.element.value
            self.psalmbord['active'] = 1
            i = 0
            for s in select_screens:
                if s.element.checked:
                    self.psalmbord['active'] = i
                i = i + 1
            save_changes()

        input_title.element.onchange = onchange
        select_fontfamily.element.onchange = onchange
        select_fontsize.element.onchange = onchange
        select_fontweight.element.onchange = onchange
        for s in select_screens:
            s.element.onchange = onchange

    def show(self):
        main.remove_childs()
        main.append(self)
        self.refresh()
