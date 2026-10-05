# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, models
from odoo.exceptions import UserError


class DocumentsDocument(models.Model):
    _inherit = "documents.document"

    def _ai_action_link_to_vehicle(self, license_plate):
        """Method to link the document to the vehicle with matching license plate."""

        self.ensure_one()
        model = 'fleet.vehicle'
        if self.res_model == model and self.res_id:
            raise UserError(_("This document is already linked to a vehicle."))
        vehicle = self.env[model].sudo().search([('license_plate', '=', license_plate)])
        if not vehicle:
            raise UserError(_("Vehicle not found: %s", license_plate))
        # sudo: document can be linked to vehicles user might not have access to
        self.with_company(self.env.company).sudo().write({
            'res_model': model,
            'res_id': vehicle.id,
            'is_editable_attachment': True,
        })
