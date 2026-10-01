# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class L10nBeNaceCode(models.Model):
    _name = 'l10n.be.nace.code'
    _description = 'BE: Nace Code'
    _rec_names_search = ('name', 'egov3_code')

    name = fields.Char(required=True, translate=True)
    egov3_code = fields.Char(required=True)

    @api.depends('egov3_code')
    def _compute_display_name(self):
        for code in self:
            code.display_name = f'[{code.egov3_code}] {code.name}'
