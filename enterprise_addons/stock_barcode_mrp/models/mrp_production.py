from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    move_raw_line_ids = fields.One2many('stock.move.line', compute='_compute_move_raw_line_ids')
    move_byproduct_line_ids = fields.One2many('stock.move.line', compute='_compute_move_byproduct_line_ids')
    is_completed = fields.Boolean(compute='_compute_is_completed')
    backorder_ids = fields.One2many(related='production_group_id.production_ids')

    @api.depends('move_raw_ids')
    def _compute_move_raw_line_ids(self):
        for order in self:
            order.move_raw_line_ids = order.move_raw_ids.move_line_ids

    @api.depends('move_byproduct_ids')
    def _compute_move_byproduct_line_ids(self):
        for order in self:
            order.move_byproduct_line_ids = order.move_byproduct_ids.move_line_ids

    @api.depends('qty_produced', 'product_qty')
    def _compute_is_completed(self):
        for order in self:
            order.is_completed = order.qty_produced == order.product_qty

    def write(self, vals):
        res = super().write(vals)
        for production in self:
            if 'qty_producing' in vals and self.env.context.get('barcode_view'):
                production.with_context(skip_raw_moves=True)._change_producing()
        return res

    def action_open_barcode_client_action(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("stock_barcode_mrp.stock_barcode_mo_client_action")
        context = {'active_id': self.id}
        return dict(action, context=context)

    def set_lot_producing(self):
        """ Special mo barcode action to produce and return SN/lot data compatible with barcode app.
        Helps avoid doing extra db calls within barcode that using action_generate_serial
        would require."""
        action = self.action_generate_serial()
        if action and action['type'] == 'ir.actions.act_window':
            return None, action
        return self.lot_producing_ids.read(self.lot_producing_ids._get_fields_stock_barcode(), load=False), action

    def _get_fields_stock_barcode(self):
        return [
            'move_raw_line_ids',
            'move_raw_ids',
            'move_byproduct_line_ids',
            'move_byproduct_ids',
            'production_location_id',
            'picking_type_id',
            'location_src_id',
            'location_dest_id',
            'product_id',
            'uom_id',
            'product_qty',
            'qty_producing',
            'lot_producing_ids',
            'name',
            'state',
            'picking_type_id',
            'company_id',
            'user_id',
            'production_group_id',
            'backorder_ids',
            'use_create_components_lots',
            'finished_move_line_ids',
        ]

    def _get_stock_barcode_data(self):
        # Avoid to get the products full name because code and name are separate in the barcode app.
        self = self.with_context(display_default_code=False)
        final_product_lines = self.finished_move_line_ids - self.move_byproduct_line_ids
        move_lines = self.move_raw_line_ids | self.move_byproduct_line_ids | final_product_lines
        lots = move_lines.lot_id | self.lot_producing_ids
        owners = move_lines.owner_id
        # Fetch all implied products in `self`
        products = self.product_id | (self.move_raw_ids + self.move_byproduct_ids).product_id
        moves = self.move_raw_ids | self.move_byproduct_ids

        uoms = products.uom_id | move_lines.uom_id | products.uom_ids | self.bom_id.uom_id | moves.bom_line_id.uom_id | products.extra_uom_ids
        # If UoM setting is active, fetch all UoM's data.
        if self.env.user.has_group('uom.group_uom'):
            uoms |= self.env['uom.uom'].search([])

        # Fetch `stock.location`
        source_locations = self.env['stock.location'].search([('id', 'child_of', self.location_src_id.ids)])
        destination_locations = self.env['stock.location'].search([('id', 'child_of', self.location_dest_id.ids)])
        scrap_location = self.env.company.scrap_location_id
        locations = move_lines.location_id | move_lines.location_dest_id | source_locations | destination_locations | self.production_location_id | scrap_location

        # Fetch `stock.package` and `stock.package.type` if group_tracking_lot.
        packages = self.env['stock.package']
        package_types = self.env['stock.package.type']
        if self.env.user.has_group('stock.group_tracking_lot'):
            packages |= move_lines.package_id | move_lines.result_package_id
            packages |= self.env['stock.package'].with_context(pack_locs=destination_locations.ids)._get_usable_packages()
            package_types = package_types.search([])

        data = {
            "records": {
                "mrp.production": self.read(self._get_fields_stock_barcode(), load=False),
                "stock.picking.type": self.picking_type_id.read(self.picking_type_id._get_fields_stock_barcode(), load=False),
                "stock.move": moves.read(moves._get_fields_stock_barcode(), load=False),
                "stock.move.line": move_lines.read(move_lines._get_fields_stock_barcode(), load=False),
                "product.product": products.read(products._get_fields_stock_barcode(), load=False),
                "res.partner": owners.read(owners._get_fields_stock_barcode(), load=False),
                "stock.location": locations.read(locations._get_fields_stock_barcode(), load=False),
                "stock.package.type": package_types.read(package_types._get_fields_stock_barcode(), False),
                "stock.package": packages.read(packages._get_fields_stock_barcode(), load=False),
                "stock.lot": lots.read(lots._get_fields_stock_barcode(), load=False),
                "uom.uom": uoms.read(uoms._get_fields_stock_barcode(), load=False),
            },
            "nomenclature_id": [self.env.company.nomenclature_id.id],
            "source_location_ids": source_locations.ids,
            "destination_locations_ids": destination_locations.ids,
        }

        data['config'] = self.picking_type_id._get_barcode_config() if self else {}
        data['line_view_id'] = self.env.ref('stock_barcode_mrp.stock_move_line_product_selector').id
        data['form_view_id'] = self.env.ref('stock_barcode_mrp.mrp_barcode_form').id
        data['header_view_id'] = self.env.ref('stock_barcode_mrp.mrp_product_selector').id
        data['scrap_view_id'] = self.env.ref('stock_barcode.scrap_product_selector').id
        data['package_view_id'] = self.env.ref('stock_barcode.stock_quant_barcode_kanban').id
        return data

    @api.model
    def filter_on_barcode(self, barcode):
        """ Searches ready MOs for the scanned product or order.
        """
        barcode_type = None
        nomenclature = self.env.company.nomenclature_id
        if nomenclature.is_gs1_nomenclature:
            parsed_results = nomenclature.parse_barcode(barcode)
            if parsed_results:
                # filter with the last feasible rule
                for result in parsed_results[::-1]:
                    if result['type'] in ('product', 'package'):
                        barcode_type = result['type']
                        break

        base_domain = [
            ('state', 'in', ['confirmed', 'progress']),
            ('reservation_state', '=', 'assigned'),
        ]

        active_id = self.env.context.get('active_id')
        additional_context = {
            'search_default_filter_confirmed': 1,
            'search_default_filter_ready': 1,
            'search_default_filter_in_progress': 1,
            'search_default_filter_to_close': 1,
            'search_default_todo': 1,
            'active_id': active_id,
        }
        picking_type = self.env['stock.picking.type'].browse(active_id)
        mo_nums = 0
        if barcode_type == 'product' or not barcode_type:
            product = self.env['product.product'].search([('barcode', '=', barcode)], limit=1)
            if product:
                mo_nums = self.search_count(base_domain + [('product_id', '=', product.id)])
                if mo_nums:
                    additional_context['search_default_product_id'] = product.id
                else:
                    mo_nums = self.search_count(base_domain + [('move_raw_ids.product_id', '=', product.id)])
                    additional_context['search_default_move_raw_ids'] = barcode
        if not barcode_type and not mo_nums:  # Nothing found yet, try to find picking by name.
            mo_nums = self.search_count(base_domain + [('name', 'ilike', barcode)])
            additional_context['search_default_name'] = barcode

        if not mo_nums:
            if barcode_type:
                return {
                    'warning': {
                        'message': _("No Manufacturing Order ready for this %(barcode_type)s", barcode_type=barcode_type),
                    }
                }
            return {
                'warning': {
                    'title': _('No product or order found for barcode %s', barcode),
                    'message': _('Scan a product to filter the orders.'),
                }
            }

        action = picking_type._get_action('stock_barcode_mrp.mrp_action_kanban')
        action['context'].update(additional_context)
        return {'action': action}

    @api.model
    def _get_new_production_client_action(self):
        action = self.env['ir.actions.actions']._for_xml_id('stock_barcode_mrp.stock_barcode_mo_client_action')
        action = dict(action, target='fullscreen')
        action['context'] = self.env.context
        return {'action': action}

    def _should_return_records(self):
        return super()._should_return_records() and not self.env.context.get('barcode_view', False)

    def action_put_in_pack(self, *, package_id=False, package_type_id=False, package_name=False, move_line_ids=[]):
        self.ensure_one()
        if self.state == 'cancel':
            raise UserError(self.env._("Manufacturing order was cancelled."))
        lines_to_pack = self.finished_move_line_ids.filtered(lambda ml: ml.product_id == self.product_id)
        if move_line_ids:
            lines_to_pack = self.env['stock.move.line'].browse(move_line_ids)
        return lines_to_pack.action_put_in_pack(package_id=package_id, package_type_id=package_type_id, package_name=package_name)

    def barcode_update_qty_producing(self, qty_producing):
        self.ensure_one()
        self.with_context(barcode_view=True).qty_producing = qty_producing
        return self.finished_move_line_ids.ids
