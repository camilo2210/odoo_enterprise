# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class L10nBeDimonaManualWizard(models.TransientModel):
    _name = 'l10n.be.dimona.manual.wizard'
    _description = 'Dimona manual Wizard'

    version_id = fields.Many2one('hr.version')
    dimona_type = fields.Selection(
        selection=[
            ('in', 'Register employee entrance'),
            ('out', 'Register employee departure'),
            ('update', 'Update employee information'),
            ('cancel', 'Cancel employee declaration'),
            ('issue', 'Fix refused declaration'),
        ])

    @api.model
    def action_open_manual_declaration(self, version):
        dimona_type = version.l10n_be_dimona_next_action
        if dimona_type not in dict(self._fields['dimona_type'].selection):
            dimona_type = False
        return {
            'type': 'ir.actions.act_window',
            'name': {
                'in': self.env._("Declare Employee Entrance"),
                'out': self.env._("Declare Employee Departure"),
                'update': self.env._("Update Employee Declaration"),
                'cancel': self.env._("Cancel Employee Declaration"),
                'issue': self.env._("Fix Refused Declaration"),
            }.get(dimona_type, self.env._("Dimona")),
            'res_model': self._name,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'default_version_id': version.id,
                'default_dimona_type': dimona_type,
            },
        }

    def submit_dimona(self):
        self.version_id.l10n_be_dimona_next_action = 'done'
