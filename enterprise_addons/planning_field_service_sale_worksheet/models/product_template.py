# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api


class ProductTemplate(models.Model):
    _inherit = "product.template"

    worksheet_template_id = fields.Many2one(
        'worksheet.template',
        string="Worksheet",
        compute='_compute_worksheet_template_id',
        readonly=False,
        store=True,
        company_dependent=True,
        domain="[('res_model', '=', 'planning.slot')]",
    )

    @api.depends('planning_enabled')
    def _compute_worksheet_template_id(self):
        for template in self:
            if not template.planning_enabled:
                template.worksheet_template_id = False
