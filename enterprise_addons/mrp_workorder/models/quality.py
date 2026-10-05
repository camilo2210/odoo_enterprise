# Part of Odoo. See LICENSE file for full copyright and licensing details.

from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tools import float_compare, float_round, is_html_empty


class QualityPointTest_Type(models.Model):
    _inherit = "quality.point.test_type"

    allow_registration = fields.Boolean(
        search='_get_domain_from_allow_registration',
        store=False, default=False)

    def _get_domain_from_allow_registration(self, operator, value):
        # The ORM will optimize the domain leaf before calling the search method:
        # ('field', '=', True) and ('field', '!=', False) become ('field', 'in', OrderedSet([True]))
        # ('field', '=', False) and ('field', '!=', True) become ('field', ' not in', OrderedSet([True]))
        if operator not in ('in', 'not in'):
            return NotImplemented
        if operator == 'in':
            return []
        else:
            return [('technical_name', 'not in', ['register_production', 'register_byproducts', 'register_consumed_materials', 'print_product_label', 'print_lot_label'])]


class MrpRoutingWorkcenter(models.Model):
    _inherit = "mrp.routing.workcenter"

    quality_point_ids = fields.One2many('quality.point', 'operation_id', copy=True)
    quality_point_count = fields.Integer('Instructions', compute='_compute_quality_point_count')

    employee_ratio = fields.Float("Employee Capacity", default=1, help="Number of employees needed to complete operation.")

    default_picking_type_ids = fields.One2many(comodel_name='stock.picking.type', compute='_compute_default_picking_type_ids')

    @api.depends('employee_ratio')
    def _compute_cost(self):
        super()._compute_cost()
        for operation in self:
            operation.cost += (operation.time_total / 60.0) * operation.workcenter_id.employee_costs_hour * (operation.employee_ratio or 1)

    @api.depends('quality_point_ids')
    def _compute_quality_point_count(self):
        read_group_res = self.env['quality.point'].sudo()._read_group(
            [('id', 'in', self.quality_point_ids.ids)],
            ['operation_id'], ['__count']
        )
        data = {operation.id: count for operation, count in read_group_res}
        for operation in self:
            operation.quality_point_count = data.get(operation.id, 0)

    def _compute_default_picking_type_ids(self):
        self.default_picking_type_ids = self.env['stock.picking.type'].search([('code', '=', 'mrp_operation')])

    def write(self, vals):
        if 'active' in vals:
            self.with_context(active_test=False).quality_point_ids.write({'active': vals['active']})
        res = super().write(vals)
        if 'bom_id' in vals:
            self.quality_point_ids._change_product_ids_for_bom(self.bom_id)
        return res

    def copy(self, default=None):
        new_workcenters = super().copy(default)
        if default and "bom_id" in default:
            for new_workcenter in new_workcenters:
                new_workcenter.quality_point_ids._change_product_ids_for_bom(new_workcenter.bom_id)
        return new_workcenters


class QualityPoint(models.Model):
    _inherit = "quality.point"

    def _default_product_ids(self):
        # Determines a default product from the default operation's BOM.
        operation_id = self.env.context.get('default_operation_id')
        if operation_id:
            bom = self.env['mrp.routing.workcenter'].browse(operation_id).bom_id
            return bom.product_id.ids if bom.product_id else bom.product_tmpl_id.product_variant_id.ids

    is_workorder_step = fields.Boolean(compute='_compute_is_workorder_step')
    operation_id = fields.Many2one(
        'mrp.routing.workcenter', 'Step', check_company=True, index='btree_not_null', ondelete='cascade')
    bom_id = fields.Many2one(related='operation_id.bom_id')
    bom_active = fields.Boolean('Related Bill of Material Active', related='bom_id.active')
    product_ids = fields.Many2many(
        default=_default_product_ids,
        domain="operation_id and [('id', 'in', bom_product_ids)] or [('type', '=', 'consu'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    bom_product_ids = fields.One2many('product.product', compute="_compute_bom_product_ids")
    test_type_id = fields.Many2one(
        'quality.point.test_type',
        domain="[('allow_registration', '=', operation_id and is_workorder_step)]")
    product_label_format = fields.Selection(
        selection='_get_product_label_format_selection',
        string="Product Label Format",
        default='pdf',
        required=True,
    )
    lot_label_format = fields.Selection(
        selection='_get_lot_label_format_selection',
        string="Lot/SN Label Format",
        default='4x12_lots',
        required=True,
    )
    worksheet_document = fields.Binary('Image/PDF')
    # Used with type register_consumed_materials the product raw to encode.
    allowed_bom_line_ids = fields.Many2many('mrp.bom.line', compute='_compute_allowed_bom_line_ids')
    bom_line_id = fields.Many2one('mrp.bom.line', domain="[('id', 'in', allowed_bom_line_ids)]")
    byproduct_id = fields.Many2one('mrp.bom.byproduct', domain="[('bom_id', 'in', bom_id)]")

    @api.model
    def _get_product_label_format_selection(self):
        return self.env['stock.picking.type']._get_mrp_product_label_to_print_selection()

    @api.model
    def _get_lot_label_format_selection(self):
        return [
            ('4x12_lots', _('4 x 12 - One per lot/SN')),
            ('4x12_units', _('4 x 12 - One per unit')),
            ('zpl_lots', _('ZPL Labels - One per lot/SN')),
            ('zpl_units', _('ZPL Labels - One per unit')),
        ]

    @api.onchange('bom_product_ids', 'is_workorder_step')
    def _onchange_bom_product_ids(self):
        if self.is_workorder_step and self.bom_product_ids:
            self.product_ids = self.product_ids & self.bom_product_ids
            self.product_category_ids = False

    @api.depends('bom_id.product_id', 'bom_id.product_tmpl_id.product_variant_ids', 'is_workorder_step', 'bom_id')
    def _compute_bom_product_ids(self):
        self.bom_product_ids = False
        points_for_workorder_step = self.filtered(lambda p: p.operation_id and p.bom_id)
        for point in points_for_workorder_step:
            bom_product_ids = point.bom_id.product_id or point.bom_id.product_tmpl_id.product_variant_ids
            point.bom_product_ids = bom_product_ids.filtered(lambda p: not p.company_id or p.company_id == point.company_id._origin)

    @api.depends('operation_id', 'picking_type_ids')
    def _compute_is_workorder_step(self):
        for quality_point in self:
            quality_point.is_workorder_step = quality_point.picking_type_ids and\
                all(pt.code == 'mrp_operation' for pt in quality_point.picking_type_ids)

    @api.depends('operation_id')
    def _compute_show_failure_location(self):
        super()._compute_show_failure_location()
        for point in self:
            point.show_failure_location = point.show_failure_location and not point.operation_id

    @api.depends('product_ids', 'bom_id', 'test_type_id')
    def _compute_allowed_bom_line_ids(self):
        self.allowed_bom_line_ids = False
        for point in self:
            if not point.bom_id or point.test_type != 'register_consumed_materials':
                continue
            allowed_bom_lines = self.env['mrp.bom.line']
            bom_products = point.bom_product_ids._origin
            if point.product_ids:
                bom_products &= point.product_ids._origin
            for product in bom_products:
                _, bom_lines = point.bom_id.explode(product, 1.0)
                allowed_bom_lines |= self.env['mrp.bom.line'].concat(l[0] for l in bom_lines)
            point.allowed_bom_line_ids = allowed_bom_lines

    def _change_product_ids_for_bom(self, bom_id):
        products = bom_id.product_id or bom_id.product_tmpl_id.product_variant_ids
        self.product_ids = [Command.set(products.ids)]

    @api.onchange('operation_id')
    def _onchange_operation_id(self):
        if self.operation_id:
            self._change_product_ids_for_bom(self.bom_id)
            self.apply_to = 'products'
        else:
            self.worksheet_document = False

    def write(self, vals):
        res = super().write(vals)
        if 'picking_type_ids' in vals:
            no_work_orders = self.filtered(lambda p: not p.is_workorder_step)
            no_work_orders.write({
                'operation_id': False,
                'worksheet_document': False
            })

        if 'test_type_id' in vals:
            for point in self:
                if point.test_type != 'register_consumed_materials' and point.bom_line_id:
                    point.bom_line_id = False
                if point.test_type != 'register_byproducts' and point.byproduct_id:
                    point.byproduct_id = False
        return res

    def action_view_worksheet_document(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Attachment Preview"),
            'res_model': 'quality.point',
            'res_id': self.id,
            'views': [(self.env.ref('mrp_workorder.quality_point_worksheet_document_preview_form').id, 'form')],
            'target': 'new',
        }


class QualityAlert(models.Model):
    _inherit = "quality.alert"

    workorder_id = fields.Many2one('mrp.workorder', 'Operation', check_company=True, index='btree_not_null')
    workcenter_id = fields.Many2one('mrp.workcenter', 'Work Center', check_company=True)
    production_id = fields.Many2one('mrp.production', "Production Order", check_company=True, index='btree_not_null')


class QualityCheck(models.Model):
    _inherit = "quality.check"

    workorder_id = fields.Many2one(
        'mrp.workorder', 'Operation', check_company=True, index='btree_not_null')
    workcenter_id = fields.Many2one('mrp.workcenter', related='workorder_id.workcenter_id')
    production_id = fields.Many2one(
        'mrp.production', 'Production Order', check_company=True, index='btree_not_null')
    product_tracking = fields.Selection(related='production_id.product_tracking')

    # doubly linked chain for tablet view navigation
    next_check_id = fields.Many2one('quality.check')
    previous_check_id = fields.Many2one('quality.check')

    # For components registration
    move_id = fields.Many2one(
        'stock.move', 'Stock Move', check_company=True, index='btree_not_null')
    component_id = fields.Many2one(
        'product.product', 'Component', check_company=True, index='btree_not_null')
    component_barcode = fields.Char(related='component_id.barcode')
    component_uom_id = fields.Many2one('uom.uom', related='move_id.uom_id', string='Component Unit', readonly=True)

    component_tracking = fields.Selection(related='component_id.tracking', string="Is Component Tracked")

    # Workorder specific fields
    is_user_working = fields.Boolean(related="workorder_id.is_user_working")
    working_state = fields.Selection(related="workorder_id.working_state")

    # Computed fields
    title = fields.Char('Title', compute='_compute_title')
    result = fields.Char('Result', compute='_compute_result')

    # Used to group the steps belonging to the same production
    # We use a float because it is actually filled in by the produced quantity at the step creation.
    finished_product_sequence = fields.Float('Finished Product Sequence Number')
    worksheet_document = fields.Binary('Image/PDF')

    # Employees
    employee_id = fields.Many2one('hr.employee', string="Employee")

    @api.model_create_multi
    def create(self, vals_list):
        quality_points = {value['point_id'] for value in vals_list if value.get('point_id')}
        quality_points_component_mapping = {}
        for point in self.env['quality.point'].browse(quality_points):
            quality_points_component_mapping[point.id] = point.bom_line_id.product_id.id or point.byproduct_id.product_id.id
        for value in vals_list:
            if value.get('component_id') or not value.get('point_id'):
                continue
            component = quality_points_component_mapping.get(value['point_id'])
            if component:
                value['component_id'] = component
        return super().create(vals_list)

    @api.depends('test_type_id', 'component_id', 'component_id.name', 'workorder_id', 'workorder_id.name')
    def _compute_title(self):
        super()._compute_title()
        for check in self:
            if not check.title and not check.point_id and check.component_id:
                check.title = '{} "{}"'.format(check.test_type_id.display_name, check.component_id.name or check.workorder_id.name)

    @api.depends('point_id', 'quality_state', 'component_id', 'component_uom_id', 'lot_ids')
    def _compute_result(self):
        for check in self:
            if check.quality_state == 'none':
                check.result = ''
            else:
                check.result = check._get_check_result()

    def copy(self, default=None):
        default = dict(default or {})
        new_checks = super().copy(default)

        for old_check, new_check in zip(self, new_checks):
            # only insert into chain if the quality check is linked with another quality check
            if old_check.previous_check_id or old_check.next_check_id:
                new_check._insert_in_chain('after', old_check)
        return new_checks

    def _get_check_result(self):
        self.ensure_one()
        if self.test_type == 'register_byproducts':
            if len(self.lot_ids) == 1:
                return f'{self.component_id.name} - {self.lot_ids[0].name}, {self.component_uom_id.name}'
            return f'{self.component_id.name}, {self.component_uom_id.name}'
        if self.test_type == 'register_consumed_materials':
            return self.env._("Success") if self.quality_state == 'pass' else self.env._("Failure")
        return ''

    def action_print(self):
        if self.test_type == 'print_product_label':
            res = self._get_product_label_action()
        elif self.test_type == 'print_lot_label':
            if self.lot_ids:
                res = self._get_lot_label_action()
            else:
                raise UserError(_('You did not set a lot/serial number for the final product'))

        # The button goes immediately to the next step
        res['next_check_id'] = self._next()
        return res

    def _get_print_qty(self):
        uom_unit = self.env.ref('uom.product_uom_unit')
        if self.product_tracking != 'serial' and self.workorder_id.uom_id._has_common_reference(uom_unit):
            qty = int(self.workorder_id.qty_producing) or int(self.workorder_id.qty_production)
        else:
            qty = 1
        return qty

    def _get_product_label_action(self):
        self.ensure_one()
        product_label_format = self.point_id.product_label_format
        if product_label_format in ('pdf', 'zpl'):
            wizard = self.env['quality.check.label.layout'].create({
                'quality_check_id': self.id,
                'print_format': '4x12' if product_label_format == 'pdf' else 'zpl',
                'with_price': False,
            })
        else:
            label_options = self.env['stock.picking.type']._get_product_label_format_options(product_label_format)
            finished_moves = self.production_id.move_finished_ids.filtered_domain([('product_id', '=', self.product_id.id)])
            wizard = self.env['product.label.layout'].create({
                'product_ids': self.product_id.ids,
                'move_ids': finished_moves.ids,
                'custom_quantity': self._get_print_qty(),
                **label_options,
            })
        return wizard.process()

    def _get_lot_label_action(self):
        lot_label_format = self.point_id.lot_label_format
        wizard = self.env['lot.label.layout'].create({
            'lot_ids': self.lot_ids.ids,
            'custom_quantity': self._get_print_qty() if '_units' in lot_label_format else 1,
            'print_format': 'zpl' if 'zpl' in lot_label_format else '4x12',
        })
        return wizard.process()

    def action_next(self):
        self.ensure_one()
        return {'next_check_id': self._next()}

    def add_check_in_chain(self, notify_bom=True):
        self.ensure_one()
        if self.workorder_id.current_quality_check_id:
            self._insert_in_chain('after', self.workorder_id.current_quality_check_id)
        else:
            self.workorder_id.current_quality_check_id = self
        if notify_bom and self.workorder_id.production_id.bom_id:
            body = _('BoM feedback (%(production)s - %(operation)s)', production=self.workorder_id.production_id.name, operation=self.workorder_id.operation_id.name)
            body += Markup("<br/>%s") % _("New Step suggested by %(user_name)s", user_name=self.env.user.name)
            if self.title:
                body += Markup("<br/><b>%s</b> %s") % (_("Title:"), self.title)
            if self.note and not is_html_empty(self.note):
                body += Markup("<br/><b>%s</b>%s") % (_("Instruction:"), self.note)
            attachments = []
            if self.worksheet_document:
                attachments = [('document', self.worksheet_document)]
            self.workorder_id.production_id.bom_id.sudo().message_post(body=body, attachments=attachments)

    def _next(self):
        """ This function:

        - first: fullfill related move line with right lot and validated quantity.
        - second: Generate new quality check for remaining quantity and link them to the original check.
        - third: Pass to the next check or return a failure message.
        """
        self.ensure_one()
        self.workorder_id.current_quality_check_id = self.id

        if self.test_type == 'picture' and not self.picture:
            raise UserError(_('Please upload a picture.'))

        if self.quality_state == 'none':
            self.do_pass()

        return self.workorder_id._change_quality_check(position='next')

    @api.ondelete(at_uninstall=False)
    def _unlink_repair_chain(self):
        for check in self:
            prev = check.previous_check_id
            nxt = check.next_check_id
            if prev and nxt:
                prev.next_check_id = nxt
                nxt.previous_check_id = prev
            elif prev:
                prev.next_check_id = False
            elif nxt:
                nxt.previous_check_id = False

    def _insert_in_chain(self, position, relative):
        """Insert the quality check `self` in a chain of quality checks.

        The chain of quality checks is implicitly given by the `relative` argument,
        i.e. by following its `previous_check_id` and `next_check_id` fields.

        :param position: Where we need to insert `self` according to `relative`
        :type position: string
        :param relative: Where we need to insert `self` in the chain
        :type relative: A `quality.check` record.
        """
        self.ensure_one()
        assert position in ['before', 'after']
        if position == 'before':
            new_previous = relative.previous_check_id
            self.next_check_id = relative
            self.previous_check_id = new_previous
            new_previous.next_check_id = self
            relative.previous_check_id = self
        else:
            new_next = relative.next_check_id
            self.next_check_id = new_next
            self.previous_check_id = relative
            new_next.previous_check_id = self
            relative.next_check_id = self

    def do_pass(self):
        res = super().do_pass()
        for check in self:
            if check.move_id:
                check.move_id.picked = True
            if check.workorder_id:
                if check.workorder_id.employee_id:
                    check.employee_id = self.workorder_id.employee_id
                if check.workorder_id.state == 'ready':
                    check.workorder_id.button_start(bypass=True)
        return res
