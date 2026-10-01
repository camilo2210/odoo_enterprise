from odoo import fields, models


class HrWorkLocation(models.Model):
    _inherit = "hr.work.location"

    zkteco_biotime_id = fields.Char(
        string="Biotime ID",
        help="The ID of the Location that is defined in the Biotime server",
    )
