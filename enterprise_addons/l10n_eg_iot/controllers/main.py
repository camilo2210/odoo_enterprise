from odoo import http
from odoo.addons.iot.controllers.main import IoTController, _search_box


class L10nEgIotController(IoTController):
    @http.route()
    def iot_box_setup(self, iot_box, devices):
        res = super().iot_box_setup(iot_box, devices)
        iot_identifier = iot_box['identifier']
        box = _search_box(iot_identifier) or _search_box(iot_box.get('mac'))

        if box and not box.l10n_eg_proxy_token:
            l10n_eg_proxy_token = iot_box.get('l10n_eg_proxy_token')
            if l10n_eg_proxy_token:
                box.l10n_eg_proxy_token = l10n_eg_proxy_token

        return res
