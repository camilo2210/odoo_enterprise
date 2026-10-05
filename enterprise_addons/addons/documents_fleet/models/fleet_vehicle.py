# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class FleetVehicle(models.Model):
    _name = 'fleet.vehicle'
    _inherit = ['fleet.vehicle', 'documents.mixin']

    def _get_document_folder(self):
        return self.company_id.documents_fleet_folder

    def _get_document_owner(self):
        """User can see only their own documents in the fleet folder (see _get_document_vals_access_rights)."""
        return self.env.user

    def _get_document_tags(self):
        return self.company_id.documents_fleet_tags

    def _check_create_documents(self):
        return self.company_id.documents_fleet_settings and super()._check_create_documents()
