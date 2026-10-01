from odoo import fields, models


class MockAccountMoveWizard(models.TransientModel):
    _name = 'mock.account.move.wizard'
    _description = "Wizard to show previews of account moves related to pay runs."

    reference = fields.Char(compute="_compute_data", string="Reference")
    accounting_date = fields.Date(compute="_compute_data", string="Accounting Date")
    journal_name = fields.Char(compute="_compute_data", string="Journal")
    line_ids = fields.One2many("mock.account.move.line", compute="_compute_data")

    def _compute_data(self):
        payrun_id = self.env.context.get('active_id') or self.env.context.get('payrun_id')

        if payrun_id:
            payrun = self.env['hr.payslip.run'].browse(payrun_id)

            move_vals_list, _ = payrun.slip_ids.filtered('journal_id')._get_account_move_vals()

            vals = move_vals_list[0]
            journal = self.env['account.journal'].browse(vals.get('journal_id'))
            vals['journal_name'] = journal.display_name

            line_commands = []
            for line in vals.get('line_ids', []):

                line_data = line[2]
                account = self.env['account.account'].browse(line_data['account_id'])
                if line_data['partner_id']:
                    partner = self.env['res.partner'].browse(line_data['partner_id'])
                else:
                    partner = False

                line_commands.append((0, 0, {
                    'company_currency_id': self.env.company.currency_id.id,
                    'account': account.display_name,
                    'partner': partner.display_name if partner else False,
                    'label': line_data['name'],
                    'debit': line_data['debit'],
                    'credit': line_data['credit'],
                    'tax_tag_ids': line_data.get('tax_tag_ids', [])
                }))
        else:
            vals = {
                'ref': False,
                'date': False,
                'journal_name': False,
            }
            line_commands = []

        self.update({
            'reference': vals.get('ref'),
            'accounting_date': vals.get('date'),
            'journal_name': vals.get('journal_name'),
            'line_ids': line_commands,
        })


class MockAccountMoveLine(models.TransientModel):
    _name = 'mock.account.move.line'
    _description = 'Mock version of an account move line used for simulations'

    company_currency_id = fields.Many2one(comodel_name='res.currency')
    account = fields.Char(string="Account")
    partner = fields.Char(string="Partner")
    label = fields.Char(string="Label")
    debit = fields.Monetary(string="Debit", currency_field="company_currency_id")
    credit = fields.Monetary(string="Credit", currency_field="company_currency_id")
    tax_tag_ids = fields.Many2many(comodel_name='account.account.tag', string="Tax Grids")
