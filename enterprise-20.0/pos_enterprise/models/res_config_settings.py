from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_module_pos_urban_piper = fields.Boolean(related='pos_config_id.module_pos_urban_piper', string="UrbanPiper", help="Manage your online orders with UrbanPiper.", readonly=False)
    module_pos_tyro = fields.Boolean(string="Tyro Payment Terminal", help="The transactions are processed by Tyro. Set your Tyro credentials on the related payment method.")
