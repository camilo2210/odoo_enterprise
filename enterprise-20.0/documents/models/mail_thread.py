# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.addons.mail.tools.discuss import Store


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def _store_thread_fields(self, res: Store.FieldList, *, request_list, **kwargs):
        super()._store_thread_fields(res, request_list=request_list, **kwargs)
        res.attr("is_documents_mixin", lambda t: issubclass(t.pool[t._name], t.pool['documents.mixin']))
