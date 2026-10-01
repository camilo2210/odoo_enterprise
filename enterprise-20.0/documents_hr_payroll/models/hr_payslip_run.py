# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    def unlink(self):
        self.env['documents.document'].search([
            ('res_model', '=', 'hr.payslip'),
            ('res_id', 'in', self.slip_ids.ids),
            ('active', '=', True),
        ]).write({
            'res_model': False,
            'res_id': False,
            'active': False,
        })
        return super().unlink()
