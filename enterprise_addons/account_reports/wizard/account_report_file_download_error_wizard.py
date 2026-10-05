# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class AccountReportFileDownloadErrorWizard(models.TransientModel):
    _name = 'account.report.file.download.error.wizard'
    _description = "Manage the file generation errors from report exports."

    actionable_errors = fields.Json()
    file_name = fields.Char()
    file_content = fields.Binary()
    has_danger_actionable_errors = fields.Boolean(compute='_compute_has_danger_actionable_errors')

    @api.depends('actionable_errors')
    def _compute_has_danger_actionable_errors(self):
        for record in self:
            record.has_danger_actionable_errors = any(error.get('level') == 'danger' for error in record.actionable_errors.values())

    def button_download(self):
        self.ensure_one()
        if self.file_name:
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/account.report.file.download.error.wizard/{self.id}/file_content/{self.file_name}?download=1',
                'close': True,
            }
