import utils
from elements import Element, element, ElementWrapper, get_Element, get_elements, get_element
from layout import home, main, set_title
E = Element

class Page(ElementWrapper):

    def __init__(self):
        super().__init__(element('div'))
        self.cameras: dict = None
        self.camid = 0

        # load wfs.js
        script = document.createElement("script")
        script.src = "/static/js/wfs.js"
        document.head.appendChild(script)

        # create html elements
        div_cams = E('div').attr('id','cams')
        div_live = E('div').attr('id','live').inner_html('Kies een camera.')
        div_presets = E('div').attr('id','presets')
        div_move = E('div').attr('id','move').attr('class','hidden').append(
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
        div_footer = E('div').attr('id','footer').attr('class','hidden').append(
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
            div_presets.remove_childs()

            ul = E('ul')
            for index, cam in enumerate(self.cameras):
                btn = E('button').inner_html(cam['name']).attr('value',index)
                btn.element.onclick = btn_presets

                ul.append(
                    E('li').append( btn )
                )
            div_cams.append( ul )

        async def btn_presets(evt):
            div_live.remove_childs()
            div_presets.remove_childs()
            div_move.attr('class','hidden')
            div_footer.attr('class','hidden')

            if evt:
                self.camid = int(evt.target.value)
            cam = self.cameras[self.camid]

            # load presets
            presets = await utils.post(utils.get_url("general/getCameraPresets"), {'id':self.camid})

            if presets['err'] in 'connection':
                div_live.inner_html("Camera is niet beschikbaar.")
            elif presets['err'] == 'fout':
                div_live.append(
                    E("div")
                    .attr("style", "color:red;")
                    .inner_html('Onverwachte fout.')
                )
            else:
                div_move.remove_attr('class')
                div_footer.remove_attr('class')

                if len(presets['presets']) == 0:
                    div_presets.append( E('p').inner_html("Geen presets") )
                else:
                    #todo
                    ul = E('ul')
                    for pr in presets['presets']:
                        btn = E('button').attr('name','p').attr('value',pr['token']).inner_html(pr['token'])
                        btn.element.onclick = goto_preset
                        lbl = E('input').attr('type','text').attr('id',pr['token']).attr('value',pr['label'])
                        lbl.element.onchange = setCameraPresetLabel

                        ul.append( E('li').append( btn,lbl ) )

                    div_presets.append( ul )
            
                # load live
                uri = await utils.post(utils.get_url("general/getCameraLive"), {'id':self.camid})

                if uri['success']:
                    ws = f"ws://{cam.url_extern}:{cam.port_ws}"
                    video = E('video').attr('id','preview').attr('data-host',ws).attr('data-stream',uri['uri']).attr('autoplay').attr('muted').attr('playsinline').attr('width','100%')
                    video.element.addEventListener(
                        "contextmenu",
                        lambda evt: evt.preventDefault()
                    )
                    div_live.remove_childs()
                    div_live.append(video)
                    
                    mediauri = ws+uri['uri']
                    __pragma__('js', '{}', '''
                        var wfs = new Wfs();
                        wfs.attachMedia(video.element, mediauri);
                    ''')
                else:
                    div_live.append(
                        E('p').inner_html(uri['error'])
                    )


        async def goto_preset(evt):
            preset = int(evt.target.value)
            result = await utils.post(utils.get_url("general/gotoCameraPreset"), {'id':self.camid, 'preset':preset})
            
            if result['success']:
                for btn in div_presets.element.querySelectorAll("button"):
                    btn.classList.remove("active")

                evt.target.classList.add("active")                

        async def setCameraPresetLabel(evt):
            token = int(evt.target.id)
            label = str(evt.target.value)

            result = await utils.post(utils.get_url("general/setCameraPresetLabel"), {'id':self.camid, 'token':token, 'label':label})
            

        async def initialize():
            self.cameras = await utils.post(utils.get_url("general/getCameras"), {})
            btn_cameras()
            btn_presets()

        self.refresh = initialize

    def show(self):
        main.remove_childs()
        main.append(self)
        self.refresh()

