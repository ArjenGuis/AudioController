import utils
from elements import Element, element, ElementWrapper, get_Element, get_elements, get_element
from layout import home, main, set_title
E = Element

class Page(ElementWrapper):

    def __init__(self):
        super().__init__(element('div'))
        self.cameras: dict = None
        cam = 0

        div_cams = E('div').attr('id','cams')
        div_live = E('div').attr('id','live')
        div_presets = E('div').attr('id','presets')
        div_move = E('div').attr('id','move')
        div_footer = E('div').attr('id','footer')

        self.append(
            div_cams,
            div_live,
            div_presets,
            div_move,
            div_footer
        )

        def btn_cameras():
            ul = E('ul')
            for index, cam in enumerate(self.cameras):
                btn = E('button').inner_html(cam['name']).attr('value',index)
                btn.element.onclick = btn_presets

                ul.append(
                    E('li').append( btn )
                )
            div_cams.append( ul )

        def btn_presets(evt):
            print(evt.target.value)
            div_presets.remove_childs()
            cam = evt.target.value
            presets = self.cameras[cam]['presets']

            if len(presets) == 0:
                div_presets.append( E('p').inner_html("Geen presets") )
            else:
                for pr in presets:
                    btn = E('button').attr('name','p').attr('value',pr['token']).inner_html(pr['token'])
                    #btn.element.onclick = 

                    div_presets.append( btn )
        

        async def initialize():
            self.cameras = await utils.post(utils.get_url("general/getCameras"), {})
            btn_cameras()

        self.refresh = initialize

    def show(self):
        main.remove_childs()
        main.append(self)
        self.refresh()

