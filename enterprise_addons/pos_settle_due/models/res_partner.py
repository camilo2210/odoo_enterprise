# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, fields, models, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    invoices_amount_due = fields.Float(
        string="Sum of customers's invoice due amount",
        compute="_compute_invoices_amount_due")

    def _compute_invoices_amount_due(self):
        commercial_partner_ids = {p.id: p.commercial_partner_id.id for p in self}
        # Fetch the sum of 'amount_residual' of unpaid invoices grouped by 'commercial_partner_id'
        invoices = self.env['account.move']._read_group(
            domain=[
                ('commercial_partner_id', 'in', set(commercial_partner_ids.values())),
                ('state', '=', 'posted'),
                ('payment_state', 'in', ('not_paid', 'partial')),
                ('move_type', 'in', ['out_invoice', 'out_receipt'])
            ],
            groupby=['commercial_partner_id'],
            aggregates=['amount_residual:sum']
        )

        due_map = {inv[0].id: inv[1] for inv in invoices}
        for partner in self:
            partner.invoices_amount_due = due_map.get(commercial_partner_ids[partner.id], 0.0)

    @api.model
    def _load_pos_data_fields(self, config):
        params = super()._load_pos_data_fields(config)
        if self.env.user.has_group('account.group_account_readonly') or self.env.user.has_group('account.group_account_invoice'):
            params += ['credit_limit', 'total_due', 'use_partner_credit_limit',
                       'commercial_partner_id', 'total_all_due', 'total_all_due_abs', 'total_all_overdue',
                       'total_due', 'total_invoiced', 'total_overdue']
        return params

    @api.model
    def _load_pos_data_read(self, records, config):
        read_records = super()._load_pos_data_read(records, config)

        if config.currency_id != self.env.company.currency_id and (self.env.user.has_group('account.group_account_readonly') or self.env.user.has_group('account.group_account_invoice')):
            for record in read_records:
                record['total_due'] = self.env.company.currency_id._convert(record['total_due'], config.currency_id, self.env.company)
        return read_records

    def _compute_has_moves(self):
        super()._compute_has_moves()
        for partner in self.filtered(lambda p: not p.has_moves):
            partner.has_moves = partner.total_due != 0

    def deposit_money_from_pos(self, session_id, payment_data):
        """
        At this point payment_data is considered as valid and processed
        from the PoS, it can be used to create account.payment on orders
        """
        self.ensure_one()
        partner = self.commercial_partner_id
        available_by_pm = {payment['payment_method_id']: payment['amount'] for payment in payment_data}
        session = self.env['pos.session'].browse(session_id)

        for pm_id, amount in available_by_pm.items():
            if amount == 0:
                continue

            pm = self.env['pos.payment.method'].browse(pm_id)
            pm._create_payment_line(
                session,
                amount,
                partner.property_account_receivable_id,
                _("Deposit money from PoS session %s", session.name),
                partner,
            )

        return True
