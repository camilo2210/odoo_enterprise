from odoo.fields import Domain

from odoo import fields, models


class HelpdeskSla(models.Model):
    _inherit = 'helpdesk.sla'

    product_ids = fields.Many2many('product.template',
        string="Services",
        domain="[('sale_ok', '=', True), ('type', '=', 'service')]",
    )
    use_helpdesk_sale_timesheet = fields.Boolean(related="team_id.use_helpdesk_sale_timesheet")

    def search_tickets_domain(self):
        domain = super().search_tickets_domain()
        product_domain = Domain.AND([
            Domain('team_id', '=', self.team_id.id),
            Domain('stage_id.sequence', '<=', self.stage_id.sequence),
            Domain('sale_line_id.product_template_id', 'in', self.product_ids.ids)
        ])

        if not self.product_ids:
            return domain
        elif not self.criteria_domain:
            return product_domain
        else:
            return Domain.OR([domain, product_domain])
