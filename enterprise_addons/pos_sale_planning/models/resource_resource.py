# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, time

from odoo import api, models, fields
from odoo.fields import Domain


class ResourceResource(models.Model):
    _name = 'resource.resource'
    _inherit = ['resource.resource', 'pos.load.mixin']

    def _get_not_invoiced_slots(self, config, partner_id=None, search=None, offset=0, **kwargs):
        domain = self._get_not_invoiced_domain(config, partner_id=partner_id, search=search, **kwargs)
        slot_ids = self.env['planning.slot'].search(domain, order='end_datetime desc', limit=20, offset=offset)
        return slot_ids

    def _get_unsearched_domain(self):
        today = fields.Date.context_today(self)
        start_of_day = datetime.combine(today, time.min)
        end_of_day = datetime.combine(today, time.max)
        return [('end_datetime', '>=', start_of_day), ('start_datetime', '<=', end_of_day)]

    def _get_not_invoiced_domain(self, config, partner_id=None, search=None, **kwargs):
        domain = [
            ('resource_ids', 'in', self.ids),
            ('state', '=', '2_published'),
            ('sale_order_id', '!=', False),
            ('sale_order_id.state', '!=', 'cancel'),
            ('sale_order_id.invoice_status', '!=', 'invoiced'),
        ]
        if config:
            domain = Domain.AND([domain, [('company_id', '=', config.company_id.id)]])
        if partner_id:
            domain = Domain.AND([domain, [('partner_id', '=', partner_id)]])
        if not search:
            domain = Domain.AND([domain, self._get_unsearched_domain()])
        else:
            domain = Domain.AND([domain, ['|', '|', ('display_name', 'ilike', search), ('resource_ids.name', 'ilike', search), ('partner_id.name', 'ilike', search)]])
        return domain

    @api.model
    def _load_pos_data_domain(self, data):
        config = self.env['pos.config'].browse(data['pos.config'].id)
        if any(config.payment_method_ids.filtered(lambda pm: pm.type == 'resource' and len(pm.resource_ids) == 0)):
            # If at least one payment method is linked to no resource meaning all resources, we load all resources.
            # We thus return an empty domain.
            return []
        resource_linked_to_payment_methods = config.payment_method_ids.filtered(lambda pm: pm.type == 'resource').resource_ids.ids
        domain = super()._load_pos_data_domain(data)
        return Domain.OR([domain, [('id', 'in', resource_linked_to_payment_methods)]])

    def get_planning_slots(self, config_id, partner_id=None, search=None, offset=0, **kwargs):
        config = self.env['pos.config'].browse(config_id)
        slot_ids = self._get_not_invoiced_slots(config, partner_id=partner_id, search=search, offset=offset, **kwargs)
        return {
            'resource.resource': self._load_pos_data_read(slot_ids.resource_ids, config),
            'planning.slot': self.env['planning.slot']._load_pos_data_read(slot_ids, config),
            'res.partner': self.env['res.partner']._load_pos_data_read(slot_ids.partner_id, config),
        }
