from odoo import fields, models
from odoo.addons.account.models.account_move import REVIEW_STATE_SELECTION


class AccountAuditAccountStatus(models.Model):
    _name = "account.audit.account.status"
    _description = "Account Audit Account Status"

    audit_id = fields.Many2one(string="Audit", comodel_name='account.return', required=True, ondelete='cascade', index="btree")
    account_id = fields.Many2one(string="Account", comodel_name='account.account', required=True, ondelete='cascade', index="btree")
    status = fields.Selection(
        selection=REVIEW_STATE_SELECTION,
    )
