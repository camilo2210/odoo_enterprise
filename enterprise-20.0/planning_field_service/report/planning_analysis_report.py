from odoo import api, fields, models
from odoo.tools import SQL
from odoo.addons.planning_field_service.models.planning_slot import SLOT_PRIORITY


class PlanningAnalysisReport(models.Model):
    _inherit = 'planning.analysis.report'

    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True)
    partner_zip = fields.Char(string='ZIP', readonly=True)
    partner_city = fields.Char(string='City', readonly=True)
    partner_street = fields.Char(string='Street', readonly=True)
    partner_street2 = fields.Char(string='Street2', readonly=True)
    partner_country_id = fields.Many2one('res.country', string='Country', readonly=True)
    partner_state_id = fields.Many2one('res.country.state', string='Customer State', readonly=True)
    priority = fields.Selection(SLOT_PRIORITY, string='Priority', readonly=True)

    @api.model
    def _select(self):
        return SQL("""%s,
            S.partner_id,
            S.priority,
            rp.zip AS partner_zip,
            rp.city AS partner_city,
            rp.street AS partner_street,
            rp.street2 AS partner_street2,
            rp.country_id AS partner_country_id,
            rp.state_id AS partner_state_id
        """, super()._select())

    @api.model
    def _join(self):
        return SQL("""%s
            LEFT JOIN res_partner rp ON rp.id = S.partner_id
        """, super()._join())

    @api.model
    def _group_by(self):
        return SQL("""%s,
            S.partner_id,
            S.priority,
            rp.zip,
            rp.city,
            rp.street,
            rp.street2,
            rp.country_id,
            rp.state_id
        """, super()._group_by())
