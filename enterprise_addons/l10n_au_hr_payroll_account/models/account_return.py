from odoo import _, Command, models


class L10NAUAccountReturn(models.Model):
    _inherit = 'account.return'

    def _compute_tax_closing_entry(self, company, options):
        move_vals_lines, tax_group_subtotal = super()._compute_tax_closing_entry(company, options)
        if company.country_code != 'AU':
            return move_vals_lines, tax_group_subtotal

        results = self.env['account.move.line']._read_group(
            domain=[
                ('date', '>=', options['date']['date_from']),
                ('date', '<=', options['date']['date_to']),
                ('company_id', '=', company.id),
                ('tax_line_id', '=', False),
                ('account_id.internal_group', 'in', ('asset', 'liability', 'equity')),
                ('move_id.state', '=', 'posted'),
                ('tax_tag_ids', 'in', ('W2', 'W3')),
            ],
            groupby=['account_id'],
            aggregates=['balance:sum'],
        )

        if not results:
            return move_vals_lines, tax_group_subtotal

        key = self._get_tax_closing_accounts(company)

        for account, balance in results:
            tax_group_subtotal[key] += balance
            move_vals_lines.append(Command.create({
                'name': _('Salary & Wages'),
                'balance': -balance,
                'account_id': account.id,
            }))

        return move_vals_lines, tax_group_subtotal
