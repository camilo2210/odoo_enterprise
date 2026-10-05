from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain
from odoo.tools import html2plaintext, is_html_empty


class StockPicking(models.Model):
    _inherit = 'stock.picking'
    _barcode_field = 'name'

    display_batch_button = fields.Boolean(compute='_compute_display_batch_button')

    @api.depends('batch_id')
    def _compute_display_batch_button(self):
        for picking in self:
            picking.display_batch_button = picking.batch_id and picking.batch_id.state == 'in_progress'

    def action_cancel_from_barcode(self):
        self.ensure_one()
        view = self.env.ref('stock_barcode.stock_barcode_cancel_operation_view')
        return {
            'name': _('Cancel this operation?'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'stock_barcode.cancel.operation',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'context': dict(self.env.context, default_picking_id=self.id),
        }

    def action_batch_pickings_from_barcode(self, picking_to_batch_ids, **kwargs):
        """ Batch current picking(s) with given pickings into either a new batch,
        either the current picking(s)' batch, then return the action to open the batch in barcode.
        :param list picking_to_batch_ids: `stock.picking` ids to batch.
        :param int product_id: since this action is called following a product's scan, this
                               parameter can help to keep track of the scanned product and thus,
                               increment one of the batched pickings' move line, and even then,
                               auto-select the line when opening the batch in the Barcode app.
        :param int qty_done:
        :param int uom_id:
        :return: An action redirecting to the batch's barcode operation.
        :rtype: dict
        """
        product_move_line = self.env['stock.move.line']
        picking_ids = set(self.ids + picking_to_batch_ids)
        pickings_to_batch = self.env['stock.picking'].browse(picking_ids)
        pickings_to_batch.picking_type_id.ensure_one()
        # Chose (or create) a batch which will contain all the pickings.
        batch = pickings_to_batch.batch_id[:1]
        if not batch:
            batch = self.env['stock.picking.batch'].create({
                'user_id': self.user_id.id,
                'company_id': self.company_id.id,
                'picking_type_id': self.picking_type_id.id,
            })
        else:
            # If a batch already exist, get all other pickings to batch them,
            # which acts like mergign multiple batches in one.
            picking_ids.update(pickings_to_batch.batch_id.picking_ids.ids)
            pickings_to_batch = self.env['stock.picking'].browse(picking_ids)

        # Batch all the pickings into a single batch, confirm it (needed if the
        # batch was created) and return the action to open it in Barcode app.
        pickings_to_batch.batch_id = batch
        batch.action_confirm()

        # If a product ID is given, find a move line of this product in the
        # batch and increment its `qty_done` to simulate a scan.
        if product_id := kwargs.get('product_id'):
            product_move_line = (batch.picking_ids - self).move_line_ids.filtered(
                lambda mvl: mvl.product_id.id == product_id and not mvl.picked
            )[0]
            qty_done = kwargs.get('qty_done', 1)
            if uom_id := kwargs.get('uom_id'):
                uom = self.env['uom.uom'].browse(uom_id)
                if uom and uom != product_move_line.uom_id:
                    qty_done = uom._compute_quantity(qty_done, product_move_line.uom_id)
            product_move_line.qty_done += qty_done

        return self.batch_id.action_client_action(product_move_line.id)

    def action_open_batch_picking(self):
        self.ensure_one()
        return self.batch_id.action_client_action()

    @api.model
    def action_open_new_picking(self):
        """ Creates a new picking of the current picking type and open it.

        :return: the action used to open the picking, or false
        :rtype: dict
        """
        context = self.env.context
        if context.get('active_model') == 'stock.picking.type':
            picking_type = self.env['stock.picking.type'].browse(context.get('active_id'))
            if picking_type.exists():
                new_picking = self._create_new_picking(picking_type)
                return new_picking.action_open_picking_client_action()
        return False

    def action_open_picking(self):
        """ method to open the form view of the current record
        from a button on the kanban view
        """
        self.ensure_one()
        view_id = self.env.ref('stock.view_picking_form').id
        return {
            'name': _('Open picking form'),
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'view_id': view_id,
            'type': 'ir.actions.act_window',
            'res_id': self.id,
        }

    def action_open_picking_client_action(self):
        """ method to open the form view of the current record
        from a button on the kanban view
        """
        self.ensure_one()
        if not self.env.user.has_group('stock.group_stock_picking_batch') and self.batch_id:
            # If picking is batched but batch setting is not enabled, open the batch instead.
            return self.batch_id.action_client_action()
        action = self.env["ir.actions.actions"]._for_xml_id("stock_barcode.stock_barcode_picking_client_action")
        context = {'active_id': self.id}
        return dict(action, context=context)

    def action_create_return_picking(self):
        """
        Create a return picking for the current picking and open it in the barcode app
        """
        self.ensure_one()
        new_picking = self._create_return()
        new_picking.action_return_all()
        new_picking.action_confirm()
        new_picking.action_assign()
        return new_picking.action_open_picking_client_action()

    def action_print_barcode(self):
        return self.action_open_label_type()

    def action_print_delivery_slip(self):
        return self.env.ref('stock.action_report_delivery').report_action(self)

    def action_print_packges(self):
        return self.env.ref('stock.action_report_picking_packages').report_action(self)

    def action_unbatch(self):
        self.ensure_one()
        if self.batch_id:
            self.batch_id = False

    def _get_stock_barcode_data(self):
        # Avoid to get the products full name because code and name are separate in the barcode app.
        self = self.with_context(display_default_code=False)
        move_lines = self.move_line_ids
        lots = move_lines.lot_id
        partners = move_lines.owner_id | self.partner_id
        # Fetch all implied products in `self` and adds last used products to avoid additional rpc.
        products = self.move_ids.product_id | move_lines.product_id

        uoms = products.uom_id | move_lines.uom_id | move_lines.packaging_uom_id | products.uom_ids | products.extra_uom_ids
        # If UoM setting is active, fetch all UoM's data.
        if self.env.user.has_group('uom.group_uom'):
            uoms |= self.env['uom.uom'].search([])

        product_uoms = products.product_uom_ids

        # Fetch `stock.location`
        source_locations = self.env['stock.location'].search([('id', 'child_of', self.location_id.ids)])
        destination_locations = self.env['stock.location'].search([('id', 'child_of', self.location_dest_id.ids)])
        package_locations = self.env['stock.location'].search([('id', 'child_of', self.location_dest_id.ids), ('usage', '!=', 'customer')])
        scrap_location = self.env.company.scrap_location_id
        locations = (
            self.location_id | self.location_dest_id | self.picking_type_id.allocated_location_id |
            self.picking_type_id.default_location_dest_id | self.picking_type_id.default_location_src_id |
            move_lines.location_id | move_lines.location_dest_id |
            source_locations | destination_locations | scrap_location
        )

        # Fetch `stock.package` and `stock.package.type` if group_tracking_lot.
        packages = self.env['stock.package']
        package_types = self.env['stock.package.type']
        if self.env.user.has_group('stock.group_tracking_lot'):
            packages |= move_lines.package_id
            packages |= self.env['stock.package'].search([('id', 'parent_of', move_lines.package_id.ids)])
            packages |= self.env['stock.package'].browse(move_lines.result_package_id._get_all_package_dest_ids())
            packages |= self.env['stock.package'].with_context(pack_locs=package_locations.ids)._get_usable_packages()
            package_types = package_types.search([])

        data = {
            "records": {
                "stock.picking": self.read(self._get_fields_stock_barcode(), load=False),
                "stock.picking.type": self.picking_type_id.read(self.picking_type_id._get_fields_stock_barcode(), load=False),
                "stock.move": self.move_ids.read(self.move_ids._get_fields_stock_barcode(), load=False),
                "stock.move.line": move_lines.read(move_lines._get_fields_stock_barcode(), load=False),
                # `self` can be a record set (e.g.: a picking batch), set only the first partner in the context.
                "product.product": products.with_context(partner_id=self[:1].partner_id.id).read(products._get_fields_stock_barcode(), load=False),
                "res.partner": partners.read(partners._get_fields_stock_barcode(), load=False),
                "stock.location": locations.read(locations._get_fields_stock_barcode(), load=False),
                "stock.package.type": package_types.read(package_types._get_fields_stock_barcode(), False),
                "stock.package": packages.read(packages._get_fields_stock_barcode(), load=False),
                "stock.lot": lots.read(lots._get_fields_stock_barcode(), load=False),
                "uom.uom": uoms.read(uoms._get_fields_stock_barcode(), load=False),
                "product.uom": product_uoms.read(product_uoms._get_fields_stock_barcode(), load=False),
            },
            "nomenclature_id": [self.env.company.nomenclature_id.id],
            "source_location_ids": source_locations.ids,
            "destination_locations_ids": destination_locations.ids,
        }
        # Extracts pickings' note if it's empty HTML.
        for picking in data['records']['stock.picking']:
            picking['note'] = False if is_html_empty(picking['note']) else html2plaintext(picking['note'])

        data['config'] = self.picking_type_id._get_barcode_config()
        data['config']['show_backorder_dialog'] = not self._should_ignore_backorders()
        data['line_view_id'] = self.env.ref('stock_barcode.stock_move_line_product_selector').id
        data['form_view_id'] = self.env.ref('stock_barcode.stock_picking_barcode').id
        data['scrap_view_id'] = self.env.ref('stock_barcode.scrap_product_selector').id
        data['package_view_id'] = self.env.ref('stock_barcode.stock_quant_barcode_kanban').id

        data['candidate_pickings_to_batch'] = self._get_suggest_batch_data()

        return data

    @api.model
    def _create_new_picking(self, picking_type):
        """ Create a new picking for the given picking type.

        :param picking_type:
        :type picking_type: :class:`~odoo.addons.stock.models.stock_picking.StockPickingType`
        :return: a new picking
        :rtype: :class:`~odoo.addons.stock.models.stock_picking.StockPicking`
        """
        # Find source and destination Locations
        location_dest_id, location_id = picking_type.warehouse_id._get_partner_locations()
        if picking_type.default_location_src_id:
            location_id = picking_type.default_location_src_id
        if picking_type.default_location_dest_id:
            location_dest_id = picking_type.default_location_dest_id

        # Create and confirm the picking
        return self.env['stock.picking'].create({
            'user_id': False,
            'picking_type_id': picking_type.id,
            'location_id': location_id.id,
            'location_dest_id': location_dest_id.id,
        })

    def _get_fields_stock_barcode(self):
        """ List of fields on the stock.picking object that are needed by the
        client action. The purpose of this function is to be overridden in order
        to inject new fields to the client action.
        """
        return [
            'company_id',
            'location_dest_id',
            'location_id',
            'move_ids',
            'move_line_ids',
            'name',
            'note',
            'origin',
            'partner_id',
            'picking_type_code',
            'picking_type_entire_packs',
            'picking_type_id',
            'picking_warning_text',
            'signature',
            'state',
            'use_create_lots',
            'use_existing_lots',
            'user_id',
        ]

    def _get_without_quantities_error_message(self):
        if self.env.context.get('barcode_view'):
            return _(
                'You cannot validate a transfer if no quantities are reserved nor done. '
                'You can use the info button on the top right corner of your screen '
                'to remove the transfer in question from the batch.'
            )
        else:
            return super()._get_without_quantities_error_message()

    @api.model
    def filter_on_barcode(self, barcode):
        """ Searches ready pickings for the scanned product/package/lot/packaging.
        """
        barcode_type = None
        nomenclature = self.env.company.nomenclature_id
        if nomenclature.is_gs1_nomenclature:
            try:
                parsed_results = nomenclature.parse_barcode(barcode)
            except ValidationError:
                parsed_results = False
            if parsed_results:
                # filter with the last feasible rule
                for result in parsed_results[::-1]:
                    if result['type'] in ('product', 'package', 'lot'):
                        barcode_type = result['type']
                        break

        active_id = self.env.context.get('active_id')
        picking_type = self.env['stock.picking.type'].browse(self.env.context.get('active_id'))
        base_domain = [
            ('picking_type_id', '=', picking_type.id),
            ('state', 'not in', ['cancel', 'done', 'draft'])
        ]
        is_lot_enabled = self.env.user.has_group('stock.group_production_lot')
        is_pack_enabled = self.env.user.has_group('stock.group_tracking_lot')
        is_uom_enabled = self.env.user.has_group('uom.group_uom')

        picking_nums = 0
        additional_context = {'active_id': active_id}
        product = None
        if barcode_type == 'product' or not barcode_type:
            product = self.env['product.product'].search([('barcode', '=', barcode)], limit=1)
            if not product and is_uom_enabled:  # Packaging barcode is also of type 'product' (barcodes unique accross product & packaging)
                product_packaging = self.env['product.uom'].search([('barcode', '=', barcode)], limit=1)
                product = product_packaging.product_id  # identify product linked with a packaging barcode
            if product:
                picking_nums = self.search_count(base_domain + [('product_id', '=', product.id)])
                additional_context['search_default_product_id'] = product.id
        if is_pack_enabled and (barcode_type == 'package' or (not barcode_type and not picking_nums)):
            package = self.env['stock.package'].search([('name', '=', barcode)], limit=1)
            if package:
                pack_domain = ['|', ('move_line_ids.package_id', '=', package.id), ('move_line_ids.result_package_id', '=', package.id)]
                picking_nums = self.search_count(base_domain + pack_domain)
                additional_context['search_default_move_line_ids'] = barcode
        if is_lot_enabled and (barcode_type == 'lot' or (not barcode_type and not picking_nums)):
            lot = self.env['stock.lot'].search([
                ('name', '=', barcode),
                '|', ('company_id', '=', False), ('company_id', '=', picking_type.company_id.id),
            ], limit=1)
            if lot:
                lot_domain = [('move_line_ids.lot_id', '=', lot.id)]
                picking_nums = self.search_count(base_domain + lot_domain)
                additional_context['search_default_lot_id'] = lot.id
        if not barcode_type and not picking_nums:  # Nothing found yet, try to find picking by name.
            picking_nums = self.search_count(base_domain + [('name', '=', barcode)])
            additional_context['search_default_name'] = barcode

        if not picking_nums:
            if barcode_type:
                return {
                    'warning': {
                        'message': _("No %(picking_type)s ready for this %(barcode_type)s", picking_type=picking_type.name, barcode_type=barcode_type),
                        'product_found': bool(product),
                    }
                }
            title, message = self._get_barcode_filter_warning(is_lot_enabled, is_pack_enabled, is_uom_enabled, barcode)
            return {
                'warning': {
                    'title': title,
                    'message': message,
                    'product_found': bool(product),
                }
            }

        action = picking_type._get_action('stock_barcode.stock_picking_action_kanban')
        action['context'].update(additional_context)
        return {'action': action}

    def _get_barcode_filter_warning(self, is_lot_enabled, is_pack_enabled, is_uom_enabled, barcode):
        if is_lot_enabled:
            if is_pack_enabled:
                if is_uom_enabled:
                    return (_("No product, lot, packaging, or package found for barcode %s", barcode),
                            _("Scan a product, a lot, a packaging, or a package to filter the transfers."))
                return (_("No product, lot, or package found for barcode %s", barcode),
                        _("Scan a product, a lot, or a package to filter the transfers."))
            elif is_uom_enabled:
                return (_("No product, lot, or packaging found for barcode %s", barcode),
                        _("Scan a product, a lot, or a packaging to filter the transfers."))
            return (_("No product or lot found for barcode %s", barcode),
                    _("Scan a product or a lot to filter the transfers."))
        elif is_pack_enabled:
            if is_uom_enabled:
                return (_("No product, package, or packaging found for barcode %s", barcode),
                        _("Scan a product, a package, or a packaging to filter the transfers."))
            return (_("No product or package found for barcode %s", barcode),
                    _("Scan a product or a package to filter the transfers."))
        elif is_uom_enabled:
            return (_("No product or packaging found for barcode %s", barcode),
                    _("Scan a product or a packaging to filter the transfers."))
        return (_("No product found for barcode %s", barcode),
                _("Scan a product to filter the transfers."))

    # BATCH SUGGEST METHODS
    def _get_candidates_for_suggest_batch_domain(self):
        domain = Domain([
            ('id', '!=', self.id),
            ('company_id', '=', self.company_id.id),
            ('picking_type_id', '=', self.picking_type_id.id),
            ('partner_id', '=', self.partner_id.id),
            ('state', '=', self.state),
        ])
        if self.batch_id:
            domain = Domain.AND([domain, Domain('batch_id', '!=', self.batch_id.id)])
        return domain

    def _get_suggest_batch_data(self):
        suggest_batch_data = []
        if self._is_candidate_for_suggest_batch():
            # Fetch sibling operations for potential batch.
            picking_domain = self._get_candidates_for_suggest_batch_domain()
            pickings = self.env['stock.picking'].search(picking_domain)
            for picking in pickings:
                unpicked_move_lines = picking.move_line_ids.filtered(lambda mv: not mv.picked)
                suggest_batch_data.append({
                    'id': picking.id,
                    'name': picking.display_name,
                    'origin': picking.origin,
                    'product_ids': unpicked_move_lines.product_id.ids,
                    'date': picking.scheduled_date,
                    'partner_name': picking.partner_id.display_name,
                })
        return suggest_batch_data

    def _is_candidate_for_suggest_batch(self):
        return (
            len(self) == 1 and
            self.partner_id and
            self.picking_type_id.code == 'incoming' and
            self.state not in ['done', 'cancel']
        )
