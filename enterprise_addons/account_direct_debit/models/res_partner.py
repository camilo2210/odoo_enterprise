from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    mandate_ids = fields.One2many(
        comodel_name='account.direct.debit.mandate',
        inverse_name='partner_id',
        help="Every direct debit mandate belonging to this partner.",
    )
    mandate_count = fields.Integer(compute='_compute_mandate_count')

    def _compute_mandate_count(self):
        mandate_data = self.env['account.direct.debit.mandate']._read_group(
            domain=[('partner_id', 'in', self.ids)],
            groupby=['partner_id'],
            aggregates=['__count'])
        mapped_data = {partner.id: count for partner, count in mandate_data}
        for partner in self:
            partner.mandate_count = mapped_data.get(partner.id, 0)

    def _get_account_statistics_count(self):
        return super()._get_account_statistics_count() + self.mandate_count

    def action_open_mandates(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('account_direct_debit.account_direct_debit_mandate_action')
        action['context'] = {
            'default_partner_id': self.id,
            'search_default_mandate_active_filter': 1,
        }
        action['domain'] = [('partner_id', '=', self.id)]
        return action
