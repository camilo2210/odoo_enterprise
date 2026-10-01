# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.portal.controllers.portal import CustomerPortal


class DocumentCustomerPortal(CustomerPortal):

    def _prepare_portal_counter_values(self, counter):
        if counter == 'document_count':
            return 'documents.document', [], 'read'
        return super()._prepare_portal_counter_values(counter)
