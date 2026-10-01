from odoo import api, models
from odoo.exceptions import UserError


class MailTemplate(models.Model):
    _inherit = 'mail.template'

    @api.ondelete(at_uninstall=False)
    def _unlink_except_reminder_master_mail_template(self):
        master_xmlids = {
            "account_followup.mail_template_invoice_payment_kind_reminder",
            "account_followup.mail_template_partner_payment_kind_reminder",
        }
        removed_xml_ids = set(self.get_external_id().values())
        if removed_xml_ids.intersection(master_xmlids):
            raise UserError(self.env._("You cannot delete this mail template, it is used in the invoice reminder sending flow."))
