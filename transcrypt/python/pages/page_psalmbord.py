__pragma__('alias', 'S', '$')  # to use jQuery library with 'S' instead of '$'
import utils
from elements import Element, element, ElementWrapper, get_Element, get_elements, get_element
from layout import home, main, set_title
from paged_list import PagedList
from dialogs import dialog_confirm
E = Element

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
fonts = ["Arial", "Cambria", "Courier New", "Courier Prime", "Georgia", "Gill Sans", "Verdana", "Samsung"]
fontsizes = list(range(5, 16))
fontweights = list(range(300, 900, 100))

# copied from settings.py
default_screens = ['leeg','regels']
default_fontsize = 8
refreshrates = [1,2,3,4,5,10,15,30,60]


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

        def regel(text: str):
            return {"text": text}

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

        div_list = E('div')
        col_1.append(div_list)
        plist = PagedList(div_list.element, "").hide_count().disable_pagination()
        plist.get_styling().table_class('table borderless')

        #config item: tekst regels
        def text_element(attr, item):
            r = E('input').attr('type', 'text').attr('style', 'width: 100%; font-family: monospace;')
            r.element.value = item[attr]

            def onchange(evt):
                item[attr] = r.element.value
                save_changes()
            r.element.onchange = onchange
            return r.element

        plist.add_column('text', 'Regels').item_to_element(text_element.bind(None, 'text'))

        def set_inputs():
            input_title.element.value = self.psalmbord['title']
            plist.get_server().data = self.psalmbord['regels']
            select_fontfamily.element.value = self.psalmbord['fontfamily']
            select_fontweight.element.value = self.psalmbord['fontweight']
            select_refreshrate.element.value = self.psalmbord['refreshrate']
            plist.refresh()

            if len(self.psalmbord['screens']) == 0:
                i = 0
                for s in default_screens:
                    add_screen('',i,s,default_fontsize,1)
                    i = i + 1
            
            i = 0
            for t in self.psalmbord['screens']:
                if i not in screen_index and t:
                    add_screen('', i, t['text'], t['size'], self.psalmbord['active'])
                elif i == self.psalmbord['active']:
                    screens = screen_div.element.querySelectorAll(".screen")
                    screens[i].querySelector("input").checked = True

                    # if stored fontsize is different, then update fontsize
                    select_fontsize = screens[i].querySelector("select")
                    if self.psalmbord['fontsize'] != select_fontsize.value:
                        self.psalmbord['fontsize'] = select_fontsize.value
                        save_changes()
                i = i + 1

        async def delete_regel(item):
            self.psalmbord['regels'].remove(item)
            await save_changes()

        async def save_changes():
            self.psalmbord = await utils.post(utils.get_url('general/setPsalmbord'), self.psalmbord)
            set_inputs()

        plist.add_button('delete', '', 'btn btn-danger btn-sm') \
            .use_element(lambda item: E('i').attr("class", 'fas fa-trash-alt')) \
            .onclick(delete_regel)

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

        # tekst regel toevoegen
        def add_regel(evt):
            self.psalmbord['regels'].append(regel(""))
            plist.get_server().data = self.psalmbord['regels']
            plist.refresh()

        button_add_regel = E('button').attr('class', 'btn btn-primary btn-sm').inner_html("Regel toevoegen")
        button_add_regel.element.onclick = add_regel

        col_1.append(button_add_regel)

        select_fontfamily = Select("fontfamily", fonts)
        select_fontweight = Select("fontweight", fontweights)
        select_refreshrate = Select("refreshrate", refreshrates)
        
        # custom screens
        screen_index = []
        screen_div = E('div').attr('class','row')

        col_1.append( 
            E('p').attr('class','psalmbord_heading').inner_html('Schermen'),
            screen_div
        )

        # add screen
        def add_screen(evt, i = None, text = '', fontsize = default_fontsize, active = None):
            if i is None:
                i = screen_div.element.querySelectorAll(".screen").length
            screen_index.append( i )

            id = f'screen{i}'
            div = E('div').attr('class','{} screen'.format(width_2)).attr('data-id',i)
            
            s = E("input").attr("class", "form-control").attr('id',id).attr("type", "radio").attr('name','active')
            if i == active:
                s.element.checked = True
            s.element.onchange = onchange
            
            select_fontsize = Select(f"fontsize{i}",fontsizes)
            select_fontsize.element.value = fontsize
            select_fontsize.element.onchange = onchange

            if i == 0 and text == 'leeg':
                l = 'Leeg'
                f = None
                d = None
                t = None
            elif i == 1 and text == 'regels':
                l = 'Met regels'
                f = E('div').append(
                        E('label').attr('style', 'width:60%').inner_html("Aantal regels"),
                        E('div').attr('style', 'display:inline-block;width:40%').append(select_fontsize)
                    )
                d = None
                t = None
            else:
                l = 'Met tekst'
                f = E('div').append(
                        E('label').attr('style', 'width:60%').inner_html("Aantal regels"),
                        E('div').attr('style', 'display:inline-block;width:40%').append(select_fontsize)
                    )
                
                d = E('button').attr('class','btn btn-danger btn-sm').attr('style','float:right; margin: 5px 0;').append( E('i').attr("class", 'fas fa-trash-alt') )
                d.element.onclick = delete_screen

                t = E('textarea').attr('name',id)
                t.element.value = text
                t.element.onchange = onchange

            div.append(
                s,
                E('label').attr('class','col-form-label').attr('for',id).inner_html( l ),
            )
            if d:
                div.append(d)
            if f:
                div.append(f)
            if t:
                div.append(t)
            
            self.psalmbord['screens'][i] = {'index':id,'text':text,'size':fontsize}
            screen_div.append( div )

        def delete_screen(evt):
            evt.target.closest(".screen").remove()
            onchange()

        button_add_screen = E('button').attr('class', 'btn btn-primary btn-sm').inner_html("Scherm toevoegen")
        button_add_screen.element.onclick = add_screen

        col_1.append(button_add_screen)

        # spacer
        col_1.append( E('p').attr('class','psalmbord_heading').inner_html('Instellingen') )

        # config settings
        col_1.append(
            E('div').attr('class', 'form-group row').append(
                E('label').attr('class', '{} col-form-label'.format(width_2)).inner_html("Lettertype"),
                E('div').attr('class', '{}'.format(width_3)).append(select_fontfamily)
            ),
            E('div').attr('class', 'form-group row').append(
                E('label').attr('class', '{} col-form-label'.format(width_2)).inner_html("Letterdikte"),
                E('div').attr('class', '{}'.format(width_3)).append(select_fontweight)
            ),
            E('div').attr('class', 'form-group row').append(
                E('label').attr('class', '{} col-form-label'.format(width_2)).inner_html("Verversen per ... seconden"),
                E('div').attr('class', '{}'.format(width_3)).append(select_refreshrate)
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
            self.psalmbord['fontsize'] = default_fontsize # default value, will be updated
            self.psalmbord['fontweight'] = select_fontweight.element.value
            self.psalmbord['active'] = 1 # default value, will be updated
            self.psalmbord['refreshrate'] = select_refreshrate.element.value
            self.psalmbord['screens'] = []

            i = 0
            for s in screen_div.element.querySelectorAll(".screen"):
                select_fontsize = s.querySelector("select")
                text = s.querySelector("textarea")
                
                if s.querySelector("input").checked:
                    self.psalmbord['active'] = i
                    self.psalmbord['fontsize'] = select_fontsize.value if select_fontsize else default_fontsize

                t = text.value if text else default_screens[i]
                f = select_fontsize.value if select_fontsize else default_fontsize

                self.psalmbord['screens'].append({'index':f"screen{i}",'text':t,'size':f})
                i = i + 1
            save_changes()

        input_title.element.onchange = onchange
        select_fontfamily.element.onchange = onchange
        select_fontweight.element.onchange = onchange
        select_refreshrate.element.onchange = onchange

    def show(self):
        main.remove_childs()
        main.append(self)
        self.refresh()
