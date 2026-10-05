from odoo import fields, models


class AccountReturn(models.Model):
    _inherit = "account.return"

    working_file_sheet_id = fields.Many2one(
        comodel_name='account.working.file.sheet',
        string="Working File Sheet",
    )

    _working_file_sheet_unique = models.Constraint(
        'UNIQUE(working_file_sheet_id)',
        "A working file sheet can only be linked to a single working file.",
    )

    def action_open_working_file_sheet(self):
        self.ensure_one()

        if not self.working_file_sheet_id:
            self.working_file_sheet_id = self.env['account.working.file.sheet']._create_spreadsheet({'account_return_id': self.id})

        return self.working_file_sheet_id.action_open_spreadsheet()
