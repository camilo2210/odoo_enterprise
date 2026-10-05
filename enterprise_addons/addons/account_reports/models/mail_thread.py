# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class MailThread(models.AbstractModel):
    _name = "mail.thread"
    _inherit = ["mail.thread"]

    def _message_post_after_hook(self, message):
        if self._name in self.env["account.report"]._get_annotatable_models() and (
            annotation_date := self.env.context.get("account_reports_annotation_date")
        ):
            self.env["account.report.annotation"].create(
                {"message_id": message.id, "date": annotation_date}
            )
        return super()._message_post_after_hook(message)

    def _message_update_content(self, message, /, *, body, **kwargs):
        super()._message_update_content(message, body=body, **kwargs)
        if (
            self._name in self.env["account.report"]._get_annotatable_models()
            and message._filter_empty()
        ):
            self.env["account.report.annotation"].sudo().search(
                [("message_id", "=", message.id)]
            ).unlink()
