from odoo import fields, models


class BankRecAutoReconcileWizard(models.TransientModel):
    _name = 'bank.rec.auto.reconcile.wizard'
    _description = 'Bank Reconciliation Auto Reconcile Wizard'

    date = fields.Date(
        string="Start Date",
        default=lambda self: fields.Date.subtract(fields.Date.today(), months=1),
    )
    journal_id = fields.Many2one(
        comodel_name='account.journal',
        string="Journal",
        domain="[('type', 'in', ('bank', 'cash', 'credit'))]",
    )

    def action_auto_reconcile(self):
        self.ensure_one()

        st_lines = self.env['account.bank.statement.line'].search([
            ('journal_id', '=', self.journal_id.id),
            ('date', '>=', self.date),
            ('date', '<=', fields.Date.today()),
            ('is_reconciled', '=', False),
            ('state', '!=', 'cancel'),
        ])
        if not st_lines:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'message': self.env._('Nothing to reconcile.'),
                },
            }

        st_lines._try_auto_reconcile_statement_lines()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': self.env._("Automatic reconciliation finished."),
                'next': {
                    'type': 'ir.actions.client',
                    'tag': 'bank_rec_reload_reconciled_lines',
                    'params': {
                        'reconciled_ids': st_lines.filtered('is_reconciled').ids,
                    },
                },
            },
        }
