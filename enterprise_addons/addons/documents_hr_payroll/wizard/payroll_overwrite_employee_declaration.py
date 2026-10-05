from odoo import models, fields


class PayrollOverwriteEmployeeDeclaration(models.TransientModel):
    _name = 'payroll.overwrite.employee.declaration'
    _description = 'Confirm Overwrite Employee Declaration'

    declaration_ids = fields.Many2many('hr.payroll.employee.declaration', 'payroll_overwrite_declaration_rel', string='Declarations')

    def action_overwrite(self):
        self.declaration_ids.write({
            'pdf_to_post': True
        })

        self.env.ref('hr_payroll.ir_cron_generate_payslip_pdfs')._trigger()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': self.env._("Overwrite confirmed. Files will be posted shortly."),
                'next': {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                },
            }
        }
