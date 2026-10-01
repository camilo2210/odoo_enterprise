# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.addons.mail.tools.discuss import Store


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def _store_thread_fields(self, res: Store.FieldList, *, request_list, **kwargs):
        super()._store_thread_fields(res, request_list=request_list, **kwargs)
        can_send_whatsapp = self.env["whatsapp.template"]._can_use_whatsapp(self._name)
        res.attr("canSendWhatsapp", can_send_whatsapp)
