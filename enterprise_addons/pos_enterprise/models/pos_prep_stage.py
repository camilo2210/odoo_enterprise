from odoo import fields, models, api


class PosPrepStage(models.Model):
    _name = 'pos.prep.stage'
    _description = 'Pos Preparation Stage'
    _inherit = ['pos.load.mixin']
    _order = 'sequence, id'

    name = fields.Char("Name", required=True)
    color = fields.Char("Color")
    alert_timer = fields.Integer(string="Alert timer (min)", help="Timer after which the order will be highlighted")
    prep_display_ids = fields.Many2many('pos.prep.display', string="Preparation displays")
    sequence = fields.Integer("Sequence")

    @api.model
    def _load_pos_preparation_data_domain(self, data):
        stage_ids = data['pos.prep.display'].stage_ids.ids
        return [('id', 'in', stage_ids)]
