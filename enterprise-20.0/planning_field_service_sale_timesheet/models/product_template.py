from odoo import models, api
from odoo.exceptions import UserError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.ondelete(at_uninstall=False)
    def _unlink_except_use_for_travel_invoice(self):
        if self.env['res.company'].search([("travel_time_invoicing_product_id", "in", self.ids), ("field_service_travel_fees", "=", True)], limit=1):
            raise UserError(self.env._("This product is required to invoice travel time for field service interventions and cannot be deleted. Please select a different product in the Planning settings or disable the Travel Time Invoicing feature before proceeding with deletion."))

    def write(self, vals):
        if (
            vals.get('type', '') != 'service'
            and (changed_products := self.filtered(lambda product: product.type == 'service').product_variant_ids)
        ):
            self.env['hr.employee'].sudo().search([('timesheet_product_id', 'in', changed_products.ids)]).timesheet_product_id = False

        if (
            'active' in vals
            and not vals['active']
            and self.env['res.company'].search([("travel_time_invoicing_product_id", "in", self.ids), ("field_service_travel_fees", "=", True)], limit=1)
        ):
            raise UserError(self.env._("This product is required to invoice travel time for field service interventions and cannot be archived. Please select a different product in the Planning settings or disable the Travel Time Invoicing feature before proceeding with archiving."))

        if (
            vals.get('company_id')
            and (companies_using_product := self.env['res.company'].search([("travel_time_invoicing_product_id", "in", self.ids), ("field_service_travel_fees", "=", True), ('id', 'not in', vals['company_id'])]))

        ):
            raise UserError(self.env._("The company for this product cannot be changed because the following companies are currently using it to invoice travel time:\n%(companies)s", companies=companies_using_product.mapped('name')))

        return super().write(vals)
