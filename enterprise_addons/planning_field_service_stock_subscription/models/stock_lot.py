from odoo import api, fields, models


class StockLot(models.Model):
    _inherit = 'stock.lot'

    subscription_ids = fields.Many2many('sale.order', string='Subscriptions', compute='_compute_subscriptions_ids', compute_sudo=True)
    subscriptions_count = fields.Integer(compute='_compute_subscriptions_ids', compute_sudo=True, export_string_translation=False)
    is_maintained = fields.Boolean(string='Maintained', compute='_compute_is_maintained', compute_sudo=True, export_string_translation=False)

    @api.depends('name', 'product_id')
    @api.depends_context('show_lot_product')
    def _compute_display_name(self):
        if not self.env.context.get('show_lot_product'):
            return super()._compute_display_name()
        for lot in self:
            lot.display_name = f"{lot.name} - {lot.product_id.display_name}"

    @api.depends('partner_ids', 'product_id')
    def _compute_subscriptions_ids(self):
        lots = self._origin
        subscription_per_lot = dict(self.env['sale.order.line']._read_group(
            [
                ('lot_ids', 'in', lots.ids),
                ('order_partner_id', 'in', lots.partner_ids.ids),
                ('order_id.is_subscription', '=', True),
            ],
            groupby=['lot_ids'],
            aggregates=['order_id:array_agg'],
        ))
        for lot in self:
            lot.subscription_ids = self.env['sale.order'].browse(sorted(set(subscription_per_lot.get(lot._origin, []))))
            lot.subscriptions_count = len(lot.subscription_ids)

    @api.depends('subscription_ids')
    def _compute_is_maintained(self):
        for lot in self:
            lot.is_maintained = any(subscription.subscription_state == '3_progress' for subscription in lot.subscription_ids)

    def action_view_subscriptions(self):
        self.ensure_one()
        action = {
            **self.env['ir.actions.actions']._for_xml_id('sale_subscription.sale_subscription_action'),
            'domain': [('id', 'in', self.subscription_ids.ids)],
            'context': {'create': False},
        }
        if len(self.subscription_ids) == 1:
            del action['views']
            action['view_mode'] = 'form'
            action['res_id'] = self.subscription_ids.id
        return action
