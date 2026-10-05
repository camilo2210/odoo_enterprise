from odoo import api, fields, models


class L10n_BeDmfa(models.Model):
    _inherit = 'l10n_be.dmfa'

    payment_id = fields.Many2one('account.payment', index='btree_not_null')

    @api.depends('payment_id', 'payment_id.state')
    def _compute_state(self):
        super()._compute_state()
        for dmfa in self:
            if dmfa.payment_id and dmfa.payment_id.state in ['paid', 'reconciled']:
                dmfa.state = 'paid'
