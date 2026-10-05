# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class FrontdeskFrontdesk(models.Model):
    _name = 'frontdesk.frontdesk'
    _inherit = ['frontdesk.frontdesk']

    frontdesk_type = fields.Selection(
        string="Type",
        selection=[("members", "Members"), ("guests", "Guests")],
        default='guests', required=True,
        help="- Members: Manage entry by Partner Level. Once configured, contacts with the required partner level can enter using their personal barcode.\n"
        "- Guests: Coordinate visitor admittance for the building (default)"
    )
    required_grade_ids = fields.Many2many('res.partner.grade', string="Grades")
    passback_timeout = fields.Float(
        string="Passback Timeout",
        default=10.0,
    )
