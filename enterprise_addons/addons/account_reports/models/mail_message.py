from odoo import models

from odoo.addons.mail.tools.discuss import Store


class MailMessage(models.Model):
    _inherit = 'mail.message'

    def _store_message_fields(self, res: Store.FieldList, **kwargs):
        super()._store_message_fields(res, **kwargs)
        if not self.env["account.report.annotation"].has_access("read"):
            return
        annotable_models = self.env["account.report"]._get_annotatable_models()
        if annotable_messages := self.filtered(lambda m: m.model in annotable_models):
            message_to_annotation_date = {
                annotation.message_id: annotation.date
                for annotation in self.env["account.report.annotation"].search_fetch(
                    [("message_id", "in", annotable_messages.ids)]
                )
            }
            res.attr(
                "account_reports_annotation_date",
                value=message_to_annotation_date.get,
                predicate=lambda m: m in annotable_messages,
            )
