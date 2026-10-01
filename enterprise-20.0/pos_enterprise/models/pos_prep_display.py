from odoo import fields, models, api, _
from odoo.exceptions import ValidationError, AccessError


class PosPrepDisplay(models.Model):
    _name = 'pos.prep.display'
    _description = 'Pos Preparation Display'
    _inherit = ["pos.bus.mixin", "pos.load.mixin"]

    name = fields.Char("Name", required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    pos_config_ids = fields.Many2many(string="Point of Sale", comodel_name='pos.config', copy=False)
    category_ids = fields.Many2many('pos.category', string="Product categories", copy=False, help="Product categories that will be displayed on this screen.")
    order_count = fields.Integer("Order count", compute='_compute_order_count')
    average_time = fields.Integer("Order average time", compute='_compute_order_count', help="Average time of all order that not in a done stage.")
    stage_ids = fields.Many2many('pos.prep.stage', string="Preparation stages")
    contains_bar_restaurant = fields.Boolean("Is a Bar/Restaurant", compute='_compute_contains_bar_restaurant', store=True)
    access_token = fields.Char("Access Token", default=lambda self: self._ensure_access_token())
    auto_clear = fields.Boolean(string='Auto clear', help='Time after which ready order will be removed from Order Status Screen.', default=False, copy=False)
    clear_time_interval = fields.Integer(string='Interval auto clear time', default=10, copy=False, help="Interval in minutes")
    printer_ids = fields.Many2many('pos.printer', string="Printers", domain="[('use_type', '=', 'preparation')]", help="Select the printer that will print the tickets from this display.")
    auto_print_stage_id = fields.Many2one('pos.prep.stage', string='Automatic Printing at', domain="[('prep_display_ids', 'in', [id])]",
        help="Automatically print a ticket when the order reaches the specified stage on the display.")
    use_barcode = fields.Boolean(string='Barcode', help="A barcode will be printed on the preparation ticket. Scanning it will move the order to the next stage.")

    @api.constrains('clear_time_interval')
    def _check_clear_time_interval_positive(self):
        for record in self:
            if record.clear_time_interval <= 0:
                raise ValidationError(_("The interval auto clear time must be positive."))

    def _load_preparation_data_models(self):
        return ['pos.category', 'pos.prep.order', 'pos.order', 'pos.order.line', 'pos.prep.line', 'pos.prep.stage', 'product.product', 'pos.preset', 'product.attribute', 'product.template.attribute.value', 'resource.calendar.attendance', 'product.attribute.custom.value', 'pos.config', 'pos.printer', 'res.users', 'ir.ui.view', 'decimal.precision']

    def load_preparation_data(self):
        metadata = self._load_metadata()
        return self._read_prep_data_from_metadata(metadata)

    def _load_metadata(self):
        models = self._load_preparation_data_models()
        records = {}
        fields = self._load_pos_preparation_data_fields()
        domain = [('id', '=', self.id)]
        records['pos.prep.display'] = {
            'domain': domain,
            'fields': fields,
            'records': self.search(domain),
            'relations': self._load_data_relations(fields),
        }
        for model in models:
            if model == 'pos.prep.display':
                continue
            try:
                self.env[model]._load_prep_metadata(records)
            except AccessError:
                records[model] = {
                    **self.env[model]._load_prep_data_domain_and_dependencies(records),
                    'records': self.env[model],
                }
        return records

    def _get_pos_config_ids(self):
        self.ensure_one()
        if not self.pos_config_ids:
            return self.env['pos.config'].search([])
        else:
            return self.pos_config_ids

    @api.model
    def _get_preparation_displays(self, posOrder, pos_categ_ids):
        config_id = posOrder.config_id.id
        return self.env['pos.prep.display'].search([
            '&',
            '|', ('pos_config_ids', '=', False),
            ('pos_config_ids', 'in', config_id),
            '|', ('category_ids', 'in', pos_categ_ids),
            ('category_ids', '=', False)])

    @api.model
    def _load_pos_data_domain(self, data):
        return [
            (
                "id",
                "in",
                [
                    display.id
                    for display in self.env["pos.prep.display"]
                    .search([])
                    .filtered(
                        lambda d: not d.pos_config_ids
                        or data['pos.config'].id in d.pos_config_ids.ids
                    )
                ],
            )
        ]

    @api.model
    def _load_pos_data_fields(self, config):
        return ['id', 'category_ids', 'write_date']

    @api.depends('stage_ids', 'pos_config_ids', 'category_ids')
    def _compute_order_count(self):
        for preparation_display in self:
            open_prep_lines = self.env['pos.prep.line'].search(preparation_display.get_preparation_display_orders_domain())
            progress_orders = open_prep_lines.filtered(lambda line: line.stage_id.id != preparation_display.stage_ids[-1].id).prep_order_id
            preparation_display.order_count = len(progress_orders)

            completed_order_times = []
            done_orders = self.env['pos.prep.order'].search([]) - open_prep_lines.prep_order_id
            for order in done_orders:
                order_lines = self.env['pos.prep.line'].search([('prep_order_id', '=', order.id), ('stage_id.id', 'in', preparation_display.stage_ids.ids)])
                if order_lines and order.pos_order_id:
                    completed_order_times.append((max(line.last_stage_change for line in order_lines) - order.pos_order_id.create_date).total_seconds())

            preparation_display.average_time = round(sum(completed_order_times) / len(completed_order_times) / 60) if completed_order_times else 0

    # if needed the user can instantly reset a preparation display and archive all the orders.
    def reset(self):
        for preparation_display in self:
            lines = self.env['pos.prep.line'].search(preparation_display.get_preparation_display_orders_domain())
            lines.write({'stage_id': False, 'last_stage_id': False, 'todo': False, 'last_stage_change': False})
            preparation_display._send_load_orders_message()

    def _send_load_orders_message(self, sound=False, notification=None, orderId=None):
        self.ensure_one()
        self._notify('LOAD_ORDERS', {'sound': sound, 'notification': notification, 'orderId': orderId})

    def open_ui(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/pos_preparation_display/web?display_id=%d' % self.id,
            'target': 'self',
        }

    def open_reset_wizard(self):
        return {
            'name': _("Reset Preparation Display"),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'pos.preparation.display.reset.wizard',
            'target': 'new',
            'context': {'prep_display_id': self.id}
        }

    def _get_preparation_display_order_additional_info(self, prep_lines):
        prep_orders = prep_lines.prep_order_id
        prep_lines |= prep_lines.combo_parent_id
        return {
            'pos.prep.line': prep_lines.read(prep_lines._load_pos_preparation_data_fields(), load=False),
            'pos.prep.order': prep_orders.read(prep_orders._load_pos_preparation_data_fields(), load=False),
            'pos.order.line': prep_lines.pos_order_line_id.read(prep_lines.pos_order_line_id._load_pos_preparation_data_fields(), load=False),
            'pos.order': prep_orders.pos_order_id.read(prep_orders.pos_order_id._load_pos_preparation_data_fields(), load=False),
            'product.product': prep_lines.product_id.read(prep_lines.product_id._load_pos_preparation_data_fields(), load=False),
            'product.template.attribute.value': prep_lines.attribute_value_ids.read(prep_lines.attribute_value_ids._load_pos_preparation_data_fields(), load=False),
            'product.attribute': prep_lines.attribute_value_ids.attribute_id.read(prep_lines.attribute_value_ids.attribute_id._load_pos_preparation_data_fields(), load=False),
            'product.attribute.custom.value': prep_lines.pos_order_line_id.custom_attribute_value_ids.read(prep_lines.pos_order_line_id.custom_attribute_value_ids._load_pos_preparation_data_fields(), load=False),
        }

    @api.constrains('stage_ids')
    def _check_stage_ids(self):
        for preparation_display in self:
            if len(preparation_display.stage_ids) == 0:
                raise ValidationError(_("A preparation display must have a minimum of one step."))
            # If any session is open, the stages cannot be modified.
            linked_pos_configs = preparation_display._get_pos_config_ids()
            if any(linked_pos_configs.mapped('session_ids').filtered(lambda s: s.state == 'opened')) and preparation_display.get_preparation_display_orders()['pos.prep.line']:
                raise ValidationError(_("You cannot modify the stages of a preparation display that has an active sessions."))

    @api.depends('pos_config_ids')
    def _compute_contains_bar_restaurant(self):
        for preparation_display in self:
            preparation_display.contains_bar_restaurant = any(pos_config_id.module_pos_restaurant for pos_config_id in preparation_display._get_pos_config_ids())

    @api.model
    def pos_has_valid_product(self):
        return self.env['product.product'].sudo().search_count([('available_in_pos', '=', True), ('list_price', '>=', 0), ('id', 'not in', self.env['pos.config']._get_special_products().ids)], limit=1) > 0

    def get_preparation_display_orders_domain(self):
        self.ensure_one()
        configs = self._get_pos_config_ids()
        sessions = configs.current_session_id
        open_orders = self.env['pos.order'].search([
            '|', ('id', 'in', sessions.order_ids.ids),
            '&', ('preset_time', '!=', False),
            ('preset_time', '>', fields.Datetime.now()),
        ])
        domain = [
            ('stage_id', 'in', self.stage_ids.ids),
            ('prep_order_id.pos_order_id', 'in', open_orders.ids),
            '!', '&', ('todo', '=', True), ('stage_id', '=', 'last_stage_id')
        ]
        if self.pos_config_ids:
            domain += [('prep_order_id.pos_order_id.config_id', 'in', self.pos_config_ids.ids)]
        if self.category_ids:
            domain += [('product_id.pos_categ_ids', 'in', self.category_ids.ids)]
        return domain

    def get_preparation_display_orders(self):
        """
        Preparation display will now only show order of the current session of
        all linked pos config. If no session is opened, the preparation display will be empty.
        """
        self.ensure_one()
        preparation_lines = self.env['pos.prep.line'].search(self.get_preparation_display_orders_domain())
        return self._get_preparation_display_order_additional_info(preparation_lines)
