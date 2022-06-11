import utils
from elements import get_element, get_elements, element, Element, ElementWrapper
import paged_list

__pragma__('alias', 'S', '$')  # to use jQuery library with 'S' instead of '$'


class Dialog(ElementWrapper):

    def __init__(self, title: str):
        super().__init__(element('div'))
        E = Element
        # warning: do not add attribute tabindex=-1 to the modal, since this conflicts with datetimepicker 'flatpickr'
        self.attr('class', "modal fade").attr("role", "dialog")

        self.title = E('h5').attr('class', 'modal-title').inner_html(title)
        self.body = E('div').attr('class', 'modal-body')
        self.footer = E('div').attr('class', 'modal-footer')

        self.modal_dialog = E('div').attr('class', 'modal-dialog').attr('role', 'document').attr('style', 'max-width:70%;').append(
            E('div').attr('class', 'modal-content').append(
                E('div').attr('class', 'modal-header').append(
                    self.title,
                    E('button').attr('type', 'button').attr('class', 'close').attr('data-dismiss', 'modal').attr('aria-label', 'Close').append(
                        E('span').inner_html("&times;")
                    )
                ),
                self.body,
                self.footer,
            )
        )
        self.append(self.modal_dialog)
        S(self.element).on('hidden.bs.modal', self.on_hide)

    def show(self):
        S(self.element).modal('show')

    def hide(self):
        S(self.element).modal('hide')

    def toggle(self):
        S(self.element).modal('toggle')

    def dispose(self):
        S(self.element).modal('dispose')
        setTimeout(lambda: self.remove_from_parent(), 2.0 * 1000.0)

    def set_title(self, title: str):
        return self.title.inner_html(title)

    def on_hide(self, *args):
        """ To be overridden by childs, if needed """
        pass

    def add_button(self, style_classes: str, text: str):
        E = Element
        button = E('button').attr('type', 'button').attr('class', style_classes).inner_html(text)
        self.footer.append(button)
        return button

    def add_button_close(self):
        return self.add_button('btn btn-secondary', 'Close').attr('data-dismiss', 'modal')

    def add_button_save(self):
        return self.add_button('btn btn-primary', 'Save')


class DialogConfirm(Dialog):
    """ Dialog to ask confirmation from user. Can be used asynchronously """

    def __init__(self, title="Bevestigen a.u.b."):
        super().__init__(title)
        button_confirm = self.add_button('btn btn-primary', 'Confirm').attr('data-dismiss', 'modal')
        button_cancel = self.add_button('btn btn-secondary', 'Cancel').attr('data-dismiss', 'modal')
        self.deferred = None
        button_confirm.element.onclick = lambda evt: self.on_button_click(True)
        button_cancel.element.onclick = lambda evt: self.on_button_click(False)

    def on_button_click(self, confirm: bool):
        if self.deferred is not None:
            self.deferred.resolve(confirm)
            self.deferred = None
        self.hide()

    async def get_confirm(self, txt: str):
        """ Ask confirmation from user

        Warning: If this function is called twice with no time in between (less then 0.5 sec),
        then the 2nd time will fail, and no dialog will be shown. This is because of the time it needs to hide (modal behavior).
        """
        # if self.deferred is not None:
        #    self.deferred.reject()
        self.body.inner_html(txt)
        self.deferred = S.Deferred()
        self.show()
        return self.deferred.promise()


dialog_confirm = DialogConfirm()


class DialogLogin(Dialog):
    """ Dialog to login """

    def __init__(self):
        super().__init__("Login")
        self.modal_dialog.element.style.maxWidth = "500px"
        E = Element
        self.deferred = None
        self.add_button_close()
        button_login = self.add_button('btn btn-primary', 'Login')
        button_login.element.onclick = lambda evt: self.on_login()

        container = E('div').attr('class', 'container')
        self.body.append(container)

        self.input_username = E('input')
        self.input_password = E('input').attr('type', 'password')

        container.append(
            E('div').attr('class', 'form-group row').append(
                E('label').inner_html("Username").attr('class', 'col-sm-3'),
                self.input_username.attr('class', 'form-control col-sm-8'),
            ),
            E('div').attr('class', 'form-group row').append(
                E('label').inner_html("Password").attr('class', 'col-sm-3'),
                self.input_password.attr('class', 'form-control col-sm-8'),
            ),
        )

    def on_login(self):
        if self.deferred is not None:
            self.deferred.resolve(
                {'username': self.input_username.element.value,
                 'password': self.input_password.element.value, })
            self.deferred = None

    def on_hide(self):
        if self.deferred is not None:
            self.deferred.reject()
            self.deferred = None

    def get_value(self):
        """ Return a dict with 'username' and 'password' """
        self.deferred = S.Deferred()
        self.show()
        return self.deferred.promise()


dialog_login = DialogLogin()


class DialogListSelect(Dialog):
    """ Dialog to select something from a list """

    def __init__(self, title, element: ElementWrapper, list: 'paged_list.PagedList'):
        super().__init__(title)
        self.list = list
        self.body.append(element)
        button_select = self.list.add_button('select', "Select", 'btn btn-primary btn-sm')
        button_select.onclick(self.on_select)
        button_close = self.add_button_close()
        button_close.element.onclick = lambda evt: self.on_select(None)
        self.deferred = None

    def on_select(self, item):
        if self.deferred is not None:
            self.deferred.resolve(item)
            self.deferred = None
        self.hide()

    async def get_value(self):
        self.deferred = S.Deferred()
        self.list.refresh()
        self.show()
        return self.deferred.promise()


class DialogSelect(Dialog):
    """ Dialog to select something and asynchronously wait for it.
    The dialog contains a html select element, so the number of options should be limited.
    If many options are needed, consider using :class:`DialogListSelect` which shows a (paginated) list.

    Example::

        # user has to choose from 'Option A' or 'Option B'
        dialog = DialogSelect([('a', 'Option A'), ('b', 'Option B')])
        result = await dialog.get_value() # returns 'a' or 'b'

    """

    def __init__(self, title: str, options):
        super().__init__(title)
        E = Element
        self.select_element = E('select').attr('class', 'form-control')
        if options is not None:
            self.set_options(options)
        self.body.append(E('div').attr('class', 'form-group').append(self.select_element))
        self.deferred = None
        self.add_button_close()
        button_next = self.add_button('btn btn-primary', 'Next')
        button_next.element.onclick = lambda evt: self.on_next(self.select_element.element.value)

    def set_options(self, options):
        E = Element
        for (value, text) in options:
            self.select_element.append(E('option').attr('value', value).inner_html(text))
        return self

    def on_next(self, selected_value):
        if self.deferred is not None:
            self.deferred.resolve(selected_value)
            self.deferred = None
        self.hide()

    async def get_value(self):
        # if self.deferred is not None:
        #    self.deferred.reject()
        self.deferred = S.Deferred()
        self.show()
        return self.deferred.promise()
