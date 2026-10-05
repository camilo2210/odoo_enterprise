# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    rental_resource_calendar_id = fields.Many2one(
        string="Rental Calendar",
        comodel_name="resource.calendar",
        default=lambda self: self.env.company.resource_calendar_id,
    )
