from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    barcode_default_snln_generation = fields.Selection([
        ('all', 'All'),
        ('only_one', 'Only One'),
    ], string='Generation Mode', default='only_one')

    barcode_allow_extra_product = fields.Boolean(
        "Allow extra products", default=True,
        help="For planned transfers, allow adding non-reserved products"
    )
    barcode_validation_after_dest_location = fields.Boolean("Force a destination for all products")
    barcode_validation_all_product_packed = fields.Boolean("Force all products to be packed")
    barcode_validation_full = fields.Boolean(
        "Allow full picking validation", default=True,
        help="Allow validating a picking even if nothing has been scanned yet, i.e. do an immediate transfer")
    restrict_scan_product = fields.Boolean(
        "Force Product scan?", help="A line's product must be scanned before the line can be edited")
    restrict_put_in_pack = fields.Selection(
        [
            ('mandatory', "After each product"),
            ('optional', "After group of products"),
            ('no', "No"),
        ], "Force put in pack?",
        help="Does the picker have to put the scanned products in a package? If yes, when?",
        default="optional", required=True)
    restrict_scan_tracking_number = fields.Selection(
        [
            ('mandatory', "Mandatory Scan"),
            ('optional', "Optional Scan"),
        ], "Force Lot/Serial scan?", default='optional', required=True)
    restrict_scan_source_location = fields.Selection(
        [
            ('no', "Optional Scan"),
            ('mandatory', "Mandatory Scan"),
        ], "Force Source Location scan?", default='no', required=True)
    restrict_scan_dest_location = fields.Selection(
        [
            ('mandatory', "After each product"),
            ('optional', "After group of products"),
            ('no', "No"),
        ], "Force Destination Location scan?",
        help="Does the picker have to scan the destination? If yes, when?",
        default='optional', required=True)
    show_barcode_validation = fields.Boolean(
        compute='_compute_show_barcode_validation',
        help='Technical field used to compute whether the "Final Validation" group should be displayed, to support combined groups/invisible complexity.')
    show_reserved_sns = fields.Boolean(
        "Show reserved lots/SN",
        help="Display reserved lots/serial numbers. When not active, the picker can pick lots/serials as they want.")
    is_barcode_picking_type = fields.Boolean(
        compute='_compute_is_barcode_picking_type',
        help="Technical field indicating if type should be used in barcode app and used to control visibility in the related UI.")
    instructions_preview = fields.Html(
        string="Instructions Preview",
        compute='_compute_instructions_preview'
    )
    group_lines_by_product = fields.Boolean("Group batch lines", help="Lines of same product at same location appear grouped. Not to use for cluster picking")

    def _compute_instructions_steps(self):
        self.ensure_one()
        steps = []
        locations_enabled = self.env.user.has_group('stock.group_stock_multi_locations')
        package_enabled = self.env.user.has_group('stock.group_tracking_lot')
        tracking_enabled = self.env.user.has_group('stock.group_production_lot')
        can_scan_source_location = locations_enabled and self.code in ('outgoing', 'internal')
        must_scan_source_location = can_scan_source_location and self.restrict_scan_source_location == 'mandatory'
        # About source location scan.
        if must_scan_source_location:
            steps.append({
                'title': _("Scan the source location")
            })
        # About product scan.
        text = ""
        if package_enabled and not self.restrict_scan_product:
            text += _("Scan an existing package to move")
        if can_scan_source_location:
            text += Markup("<br/>") if text else ""
            text += _("Scan a source location")
        steps.append({
            'title': _("Scan a product"),
            'optional': not self.restrict_scan_product,
            'alternative_text': text,
        })
        # About lot/serial number scan.
        if tracking_enabled:
            steps.append({
                'title': _("Scan a lot/serial number if product is tracked")
            })
            text = False
            if package_enabled and self.restrict_put_in_pack == 'optional':
                text = _("Scan a package or put in pack if desired")
            steps.append({
                'title': _("Scan more lot/serial numbers"),
                'optional': True,
                'alternative_text': text,
            })
        # About Put in Pack.
        if package_enabled and self.restrict_put_in_pack == 'mandatory':
            steps.append({
                'title': _("Scan a package or put in pack"),
            })
        # About destination location.
        if locations_enabled and self.restrict_scan_dest_location != 'no':
            steps.append({
                'title': _("Scan the destination location"),
                'optional': self.restrict_scan_dest_location == 'optional',
            })
        # About validation.
        steps.append({
            'title': _("Validate or scan another product"),
            'alternative_text': must_scan_source_location and _("Scan another source location"),
        })
        return steps

    @api.depends('code', 'restrict_put_in_pack', 'restrict_scan_product', 'restrict_scan_dest_location', 'restrict_scan_source_location')
    def _compute_instructions_preview(self):
        self.instructions_preview = False
        for picking_type in self:
            if picking_type.code not in ['incoming', 'outgoing', 'internal']:
                continue
            steps = picking_type._compute_instructions_steps()
            if steps:
                # Compute the description in HTML.
                html_parts = [Markup('<ol>')]
                for step in steps:
                    html_parts.append(Markup('<li><div class="o_barcode_instruction"><strong>%s</strong>') % step['title'])
                    if step.get('optional'):
                        html_parts.append(f' {_("(optional)")}')
                    if alternative_text := step.get('alternative_text'):
                        html_parts.append(Markup('<div class="text-muted">%s<br/>%s</div>') % (_("Alternative:"), alternative_text))
                    html_parts.append(Markup('</div></li>'))
                html_parts.append(Markup('</ol>'))
                picking_type.instructions_preview = (Markup().join(html_parts))

    @api.depends('restrict_scan_product', 'restrict_put_in_pack', 'restrict_scan_dest_location')
    def _compute_show_barcode_validation(self):
        for picking_type in self:
            # reflect all fields invisible conditions
            hide_full = picking_type.restrict_scan_product
            hide_all_product_packed = not self.env.user.has_group('stock.group_tracking_lot') or\
                                      picking_type.restrict_put_in_pack != 'optional'
            hide_dest_location = not self.env.user.has_group('stock.group_stock_multi_locations') or\
                                 (picking_type.code == 'outgoing' or picking_type.restrict_scan_dest_location != 'optional')
            # show if not all hidden
            picking_type.show_barcode_validation = not (hide_full and hide_all_product_packed and hide_dest_location)

    @api.depends('code')
    def _compute_is_barcode_picking_type(self):
        for picking_type in self:
            if picking_type.code in ['incoming', 'outgoing', 'internal']:
                picking_type.is_barcode_picking_type = True
            else:
                picking_type.is_barcode_picking_type = False

    @api.constrains('restrict_scan_source_location', 'restrict_scan_dest_location')
    def _check_restrinct_scan_locations(self):
        for picking_type in self:
            if picking_type.code == 'internal' and\
               picking_type.restrict_scan_dest_location == 'optional' and\
               picking_type.restrict_scan_source_location == 'mandatory':
                raise UserError(_("If the source location must be scanned, then the destination location must either be scanned after each product or not scanned at all."))

    def action_picking_batch_barcode_kanban(self):
        action = self._get_action('stock_barcode.stock_barcode_batch_picking_action_kanban')
        return action

    def get_action_picking_tree_ready_kanban(self):
        return self._get_action('stock_barcode.stock_picking_action_kanban')

    def _get_barcode_config(self):
        self.ensure_one()
        # Defines if all lines need to be packed to be able to validate a transfer.
        locations_enable = self.env.user.has_group('stock.group_stock_multi_locations')
        lines_need_to_be_packed = self.env.user.has_group('stock.group_tracking_lot') and (
            self.restrict_put_in_pack == 'mandatory' or (
                self.restrict_put_in_pack == 'optional'
                and self.barcode_validation_all_product_packed
            )
        )
        lines_need_destination_location = locations_enable and (
            self.restrict_scan_dest_location == 'mandatory' or (
                self.restrict_scan_dest_location == 'optional'
                and self.barcode_validation_after_dest_location
            )
        )
        config = {
            # Boolean fields.
            'barcode_allow_extra_product': self.barcode_allow_extra_product,
            'barcode_validation_after_dest_location': locations_enable and self.barcode_validation_after_dest_location,
            'barcode_validation_all_product_packed': self.barcode_validation_all_product_packed,
            'barcode_validation_full': not self.restrict_scan_product and self.barcode_validation_full,  # Forced to be False when scanning a product is mandatory.
            'create_backorder': self.create_backorder,
            'group_lines_by_product': self.group_lines_by_product,
            'restrict_scan_product': self.restrict_scan_product,
            'batch_enable': self.env.user.has_group('stock.group_stock_picking_batch'),
            # Selection fields converted into boolean.
            'restrict_scan_tracking_number': self.restrict_scan_tracking_number == 'mandatory',
            'restrict_scan_source_location': locations_enable and self.restrict_scan_source_location == 'mandatory',
            # Selection fields.
            'restrict_put_in_pack': self.restrict_put_in_pack,
            'restrict_scan_dest_location': self.restrict_scan_dest_location if locations_enable else 'no',
            # Additional parameters.
            'allocated_location_id': self.allocated_location_id.id,
            'lines_need_to_be_packed': lines_need_to_be_packed,
            'lines_need_destination_location': lines_need_destination_location,
        }
        return config

    def _get_fields_stock_barcode(self):
        return [
            'default_location_dest_id',
            'default_location_src_id',
            'use_create_lots',
            'use_existing_lots',
            'show_reserved_sns',
            'barcode_default_snln_generation',
            'restrict_scan_tracking_number',
        ]

    def get_model_records_count(self, res_model):
        self.ensure_one()
        assert res_model in ['stock.picking', 'stock.picking.batch']

        if res_model == 'stock.picking':
            return self.count_picking_ready

        return self.env['stock.picking.batch'].search_count([
            ('picking_type_id', '=', self.id),
            ('user_id', 'in', [self.env.user.id, False]),
            ('state', '=', 'in_progress'),
        ])
