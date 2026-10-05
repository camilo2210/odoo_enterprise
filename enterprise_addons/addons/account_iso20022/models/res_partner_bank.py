from odoo import api, fields, models


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    is_third_party = fields.Boolean(
        compute="_compute_is_third_party",
        store=True,
        readonly=False,
        string='Third-Party Account',
        help="Account owned by someone else than the employee"
    )
    third_party_beneficiary_id = fields.Many2one(
        'res.partner',
        string='Third-Party Beneficiary',
        help="Entity managing the third-party account"
    )
    partner_name = fields.Char(related='partner_id.name')

    @api.depends('partner_id.name', 'holder_name')
    def _compute_is_third_party(self):
        for record in self:
            if record.holder_name == record.partner_id.name:
                record.is_third_party = False
