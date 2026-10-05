from odoo import api, fields, models, Command
from odoo.exceptions import UserError


class AccountWorkingFileSheet(models.Model):
    _name = "account.working.file.sheet"
    _description = "Working File Sheet"
    _inherit = ['spreadsheet.mixin']

    return_id = fields.One2many(
        comodel_name='account.return',
        inverse_name='working_file_sheet_id',
        readonly=True,
    )

    @api.depends('return_id.name')
    def _compute_display_name(self):
        for spreadsheet in self:
            spreadsheet.display_name = spreadsheet.return_id.name

    @api.model
    def _create_spreadsheet(self, vals=None):
        if vals is None:
            vals = {}

        account_return_id = vals.get('account_return_id')
        if not account_return_id:
            raise UserError(self.env._("No account return was provided when creating a working file sheet."))
        vals.pop('account_return_id')

        return self.create({
            'return_id': [Command.link(account_return_id)],
            **vals,
        })

    @api.model
    def action_open_new_spreadsheet(self, vals=None):
        spreadsheet = self._create_spreadsheet(vals)
        action_open = spreadsheet.action_open_spreadsheet()
        return action_open

    def action_open_spreadsheet(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'action_open_working_file_sheet',
            'params': {
                'spreadsheet_id': self.id,
            }
        }

    @api.model
    def _get_spreadsheet_selector(self):
        working_file_id = self.env.context.get('working_file_id')
        selector = {
            'model': self._name,
            'display_name': self.env._("Working Files"),
            'sequence': -1 if working_file_id else 99,
            'component': 'WorkingFilePage',
        }

        if working_file_id:
            selector['additional_props'] = {
                'workingFileId': working_file_id,
            }

        return selector
