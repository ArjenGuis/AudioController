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
        div_move = E('div').attr('id','move').append(
            E('div').append(
                E('button').attr('id','leftup').attr('class','ptzmove tl'),
                E('button').attr('id','up').attr('class','ptzmove tm'),
                E('button').attr('id','rightup').attr('class','ptzmove tr'),
            ),
            E('div').append(
                E('button').attr('id','left').attr('class','ptzmove ml'),
                E('button').attr('id','stop').attr('class','ptzmove mm'),
                E('button').attr('id','right').attr('class','ptzmove mr'),
            ),
            E('div').append(
                E('button').attr('id','leftdown').attr('class','ptzmove bl'),
                E('button').attr('id','down').attr('class','ptzmove bm'),
                E('button').attr('id','rightdown').attr('class','ptzmove br'),
            ),
            E('div').append(
                E('button').attr('id','zoomdec').attr('class','ptzmove zoomout'),
                E('div').attr('class','ptzmove'),
                E('button').attr('id','zoomadd').attr('class','ptzmove zoomin'),
            ),
        )
        div_footer = E('div').attr('id','footer').append(
            E('p').append( E('label').append(
                E('input').attr('type','checkbox').attr('name','streampublish').attr('value','1'),
                E('span').inner_html(' Live uitzenden')
            ) ),
            E('p').append( E('button').attr('id','reboot').inner_html('Herstarten') )
        )

        self.append(
            div_cams,
            div_live,
            div_presets,
            div_move,
            div_footer
        )

        def btn_cameras():
            div_cams.remove_childs()

            ul = E('ul')
            for index, cam in enumerate(self.cameras):
                btn = E('button').inner_html(cam['name']).attr('value',index)
                btn.element.onclick = btn_presets

                ul.append(
                    E('li').append( btn )
                )
            div_cams.append( ul )

        def btn_presets(evt):
            div_presets.remove_childs()
            cam = evt.target.value
            presets = self.cameras[cam]['presets']

            if len(presets) == 0:
                div_presets.append( E('p').inner_html("Geen presets") )
            else:
                #todo
                ul = E('ul')
                for pr in presets:
                    btn = E('button').attr('name','p').attr('value',pr['token']).inner_html(pr['token'])
                    #btn.element.onclick = 
                    lbl = E('input').attr('type','text').attr('value',pr['name'])
                    #lbl.onchange = 

                    ul.append( E('li').append( btn, lbl ) )

                div_presets.append( ul )


        async def initialize():
            self.cameras = await utils.post(utils.get_url("general/getCameras"), {})
            btn_cameras()

        self.refresh = initialize

    def show(self):
        main.remove_childs()
        main.append(self)
        self.refresh()

