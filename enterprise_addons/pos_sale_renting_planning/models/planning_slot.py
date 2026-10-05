from odoo import fields, models, api


class PlanningSlot(models.Model):
    _inherit = 'planning.slot'

    rental_status = fields.Selection(related="sale_line_id.rental_status")

    @api.model
    def _load_pos_data_fields(self, config_id):
        return super()._load_pos_data_fields(config_id) + ['rental_status']
