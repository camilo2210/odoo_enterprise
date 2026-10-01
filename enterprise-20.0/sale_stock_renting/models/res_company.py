# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # Rental Inventory

    rental_loc_id = fields.Many2one(
        "stock.location",
        string="Rental Location",
        domain=[('usage', '=', 'internal')],
        help="This technical location serves as stock for products currently in rental."
        " This location is internal because products in rental are still considered as"
        " company assets.",
    )

    def _create_per_company_locations(self):
        super()._create_per_company_locations()
        self._create_rental_location()

    @api.model
    def create_missing_rental_location(self):
        companies_without_rental_location = self.env['res.company'].search([
            ('rental_loc_id', '=', False)
        ])
        companies_without_rental_location._create_rental_location()

    def _create_rental_location(self):
        rental_loc_values = [
            {
                "name": self.env._("Rental"),
                "usage": "internal",
                "company_id": company.id,
                "location_id": self.env.ref('stock.stock_location_customers').id,
            }
            for company in self.sudo()
            if not company.rental_loc_id
        ]
        if not rental_loc_values:
            return
        rental_loc_ids = self.env['stock.location'].sudo().create(rental_loc_values)
        company_rental_loc = {loc.company_id.id: loc for loc in rental_loc_ids}
        for company in rental_loc_ids.company_id:
            company.rental_loc_id = company_rental_loc.get(company.id, False)
