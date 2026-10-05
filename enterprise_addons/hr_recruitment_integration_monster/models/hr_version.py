# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields


class HrVersion(models.Model):
    _inherit = 'hr.version'

    monster_id = fields.Integer(
        string='Monster ID', help='Monster ID of the contract type.', groups='hr.group_hr_manager')

    @api.model
    def _get_whitelist_fields_from_template(self):
        return super()._get_whitelist_fields_from_template() + ['monster_id']
