# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, _


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    move_id = fields.Many2one('account.move', readonly=True, index='btree_not_null')
    move_state = fields.Selection(related='move_id.state', string='Move State')
    batch_payroll_move_lines = fields.Boolean(related='company_id.batch_payroll_move_lines')

    def action_open_move(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Journal Entry'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.move_id.id,
        }
