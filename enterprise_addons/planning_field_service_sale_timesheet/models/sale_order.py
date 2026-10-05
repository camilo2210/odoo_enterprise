# Part of Odoo. See LICENSE file for full copyright and licensing details.
from collections import defaultdict

from odoo import api, fields, models
from odoo.tools.float_utils import float_is_zero


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    planning_slot_id = fields.Many2one(
        'planning.slot',
        'Source Intervention',
        help="Intervention from which this quotation have been created",
    )
    intervention_count = fields.Integer(compute='_compute_intervention_count', export_string_translation=True, groups='planning.group_planning_user')
    completed_intervention_count = fields.Integer(compute='_compute_intervention_count', export_string_translation=True, groups='planning.group_planning_user')

    def _compute_intervention_count(self):
        intervention_count_by_order, completed_intervention_count_by_order = defaultdict(int), defaultdict(int)
        for sale_order, state, count in self.env['planning.slot']._read_group(
            [
                ('sale_order_id', 'in', self.ids),
                ('start_datetime', '!=', False),
                ('end_datetime', '!=', False),
            ],
            ['sale_order_id', 'state'],
            ['__count'],
        ):
            intervention_count_by_order[sale_order.id] += count
            if state == '4_completed':
                completed_intervention_count_by_order[sale_order.id] += count

        for sale_order in self:
            sale_order.intervention_count = intervention_count_by_order.get(sale_order.id, 0)
            sale_order.completed_intervention_count = completed_intervention_count_by_order.get(sale_order.id, 0)

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        for sale_order in orders:
            if sale_order.planning_slot_id:
                message = self.env._("Quotation Created: %s", sale_order._get_html_link())
                sale_order.planning_slot_id.message_post(body=message)
        return orders

    def message_post(self, **kwargs):
        if self.env.context.get('fsm_no_message_post'):  # TODO: change the context key
            return False
        return super().message_post(**kwargs)

    def action_confirm(self):
        res = super().action_confirm()
        for sale_order in self:
            if sale_order.planning_slot_id:
                sale_order.message_post_with_source(
                    'mail.message_origin_link',
                    render_values={'self': sale_order, 'origin': sale_order.planning_slot_id},
                    subtype_xmlid='mail.mt_note',
                )
        return res

    def _compute_invoice_status(self):
        super()._compute_invoice_status()
        material_feature_enabled = self.env['res.groups']._is_feature_enabled(
            'planning.group_field_service_allow_material'
        )
        confirmed_orders_with_intervention_not_invoiced = self.filtered(
            lambda so:
                so.state == 'sale'
                and any(sol.planning_slot_id for sol in so.order_line)
                and so.invoice_status not in ('invoiced', 'upselling')
                and not so.company_id.anglo_saxon_accounting
                and material_feature_enabled
        )
        if not confirmed_orders_with_intervention_not_invoiced:
            return
        material_sale_data_by_planning_slot = confirmed_orders_with_intervention_not_invoiced.order_line.planning_slot_id.sudo()._get_material_data_sale_order_by_planning_slot()
        fully_invoiced_orders = confirmed_orders_with_intervention_not_invoiced.filtered(
            lambda so:
                all(
                    (
                        sol.invoice_status == 'invoiced'
                        or (
                            sol.invoice_status == 'no'
                            and sol.planning_slot_id
                            and sol in material_sale_data_by_planning_slot.get(sol.planning_slot_id, {}).get(sol.order_id, {}).get('material_sale_lines', self.env['sale.order.line'])
                            and float_is_zero(sol.price_unit, precision_rounding=sol.currency_id.rounding)
                        )
                    ) for sol in so.order_line
                )
        )
        fully_invoiced_orders.invoice_status = 'invoiced'

    def action_add_from_catalog(self):
        if (
            self.planning_slot_id.has_access('write')
            and len(self.planning_slot_id) == 1
            and self.env['res.groups']._is_feature_enabled(
                'planning.group_field_service_allow_material'
            )
        ):
            return self.planning_slot_id.action_view_material()
        return super().action_add_from_catalog()
