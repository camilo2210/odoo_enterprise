
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class QualitySpreadsheetTemplate(models.Model):
    _name = 'quality.spreadsheet.template'
    _description = "Quality check template spreadsheet"
    _inherit = ['spreadsheet.mixin']

    name = fields.Char(required=True, default=lambda self: self.env._('Untitled spreadsheet'))
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company
    )
    check_cell = fields.Char(
        string="Success cell",
        default='A1',
        help="The check is successful if the success cell value is TRUE. If there are"
        " several sheets, specify which one you want to use (e.g. Sheet2!C4). If not "
        "specified, the first sheet is selected by default.",
    )

    def get_record_default_action(self, access_uid=None):
        return self.action_open_spreadsheet()

    def action_open_spreadsheet(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'action_quality_spreadsheet_template',
            'params': {
                'spreadsheet_id': self.id,
            },
        }

    def _get_spreadsheet_metadata(self, access_token=None):
        data = super()._get_spreadsheet_metadata(access_token)
        data['quality_check_cell'] = self.check_cell
        return data

    @api.model
    def _get_spreadsheet_selector(self):
        if self.search_count([], limit=1):
            return {
                'model': self._name,
                'display_name': _("Quality templates"),
                'sequence': 30,
                'allow_create': False,
            }
