# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class MailingFilter(models.Model):
    _inherit = 'mailing.filter'

    # Override: include marketing.campaign models
    mailing_model_id = fields.Many2one(domain="['|', '&', ('is_mail_thread', '=', True), ('model', '!=', 'mail.blacklist'), ('is_mailing_enabled', '=', True)]")
