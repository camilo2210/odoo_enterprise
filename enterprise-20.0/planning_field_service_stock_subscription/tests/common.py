from odoo import Command
from odoo.addons.sale_subscription.tests.common_sale_subscription import SaleSubscriptionCommon


class MaintenanceContractCommon(SaleSubscriptionCommon):
    """ A subscription selling serialised machines, delivered to their owner.

        `self.contract` is that subscription, `self.contract_line` its recurring service
        line, and `self.lot_1` / `self.lot_2` the two machines it ends up covering.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['res.config.settings'].create({
            'group_field_service_allow_equipment': True,
            'group_field_service_allow_maintenance_contract': True,
        }).execute()

        cls.customer, cls.other_customer = cls.env['res.partner'].create([
            {'name': 'Machine Owner'},
            {'name': 'Another Machine Owner'},
        ])
        cls.machine = cls.env['product.product'].create({
            'name': 'Serialised Machine',
            'is_storable': True,
            'tracking': 'serial',
            'recurring_invoice': False,
        })
        cls.maintenance = cls.env['product.product'].create({
            'name': 'Maintenance Contract',
            'type': 'service',
            'recurring_invoice': True,
        })
        cls.consultancy = cls.env['product.product'].create({
            'name': 'One Shot Consultancy',
            'type': 'service',
            'recurring_invoice': False,
        })

        cls.contract = cls._sell_machines_under_contract(cls.customer, ['SN-1', 'SN-2'])
        cls.contract_line = cls.contract.order_line.filtered(lambda line: line.product_id == cls.maintenance)
        cls.lot_1, cls.lot_2 = cls.contract_line.lot_ids.sorted('name')

    @classmethod
    def _sell_machines_under_contract(cls, partner, serials, deliver=True, extra_lines=(), subscription=True):
        """ Sell one machine per serial along with a maintenance contract, and deliver them. """
        cls._put_in_stock(serials)
        order = cls.env['sale.order'].create({
            'partner_id': partner.id,
            'plan_id': cls.plan_month.id if subscription else False,
            'order_line': [
                Command.create({'product_id': cls.machine.id, 'product_uom_qty': len(serials)}),
                Command.create({'product_id': cls.maintenance.id, 'product_uom_qty': 1}),
                *(Command.create(vals) for vals in extra_lines),
            ],
        })
        order.action_confirm()
        if deliver:
            cls._deliver(order, serials)
        return order

    @classmethod
    def _put_in_stock(cls, serials):
        """ One machine on hand per serial, so that the delivery has something to reserve. """
        lots = cls.env['stock.lot'].create([{
            'name': serial,
            'product_id': cls.machine.id,
            'company_id': cls.env.company.id,
        } for serial in serials])
        for lot in lots:
            cls.env['stock.quant']._update_available_quantity(
                cls.machine, cls.env.ref('stock.stock_location_stock'), 1.0, lot_id=lot,
            )
        return lots

    @classmethod
    def _deliver(cls, order, serials):
        """ Validate the outgoing transfer of `order`, handing over exactly `serials`. """
        lots = cls.env['stock.lot'].search([
            ('product_id', '=', cls.machine.id), ('name', 'in', list(serials)),
        ])
        picking = order.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel'))
        picking.action_assign()
        move = picking.move_ids.filtered(lambda m: m.product_id == cls.machine)
        move.move_line_ids.unlink()
        cls.env['stock.move.line'].create([{
            'move_id': move.id,
            'picking_id': picking.id,
            'product_id': cls.machine.id,
            'location_id': move.location_id.id,
            'location_dest_id': move.location_dest_id.id,
            'quantity': 1,
            'lot_id': lot.id,
        } for lot in lots])
        move.picked = True
        picking.button_validate()
        return picking
