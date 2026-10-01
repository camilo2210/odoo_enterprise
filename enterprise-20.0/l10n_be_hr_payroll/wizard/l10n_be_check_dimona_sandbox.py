# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, _
from odoo.exceptions import UserError
import json


class l10nBeCheckDimonaSandbox(models.TransientModel):
    _name = 'l10n.be.check.dimona.sandbox'
    _description = 'Dimona Check Status Sandbox Wizard'

    version_id = fields.Many2one('hr.version', string='Employee Record', required=True)
    declaration_id = fields.Many2one('l10n.be.dimona.declaration', string='Declaration', related='version_id.l10n_be_last_dimona_declaration_id')
    response_json = fields.Text(string='Declaration Response (JSON)', help='Edit the JSON response to simulate different DIMONA status checks in sandbox mode')

    def apply_response(self):
        self.ensure_one()
        try:
            response_data = json.loads(self.response_json)
        except json.JSONDecodeError as e:
            raise UserError(_("Invalid JSON format: %s", str(e)))

        self.version_id.l10n_be_last_dimona_declaration_id.content = response_data
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'hr.employee',
            'res_id': self.version_id.employee_id.id,
            'target': 'current',
        }
