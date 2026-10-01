from collections import defaultdict

from odoo import api, fields, models
from odoo.addons.timer.utils.timer_utils import round_time_spent
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tools import SQL, float_round, format_date, OrderedSet
from odoo.tools.misc import unquote


class PlanningSlot(models.Model):
    _inherit = 'planning.slot'

    def _domain_sale_line_id(self):
        domain = super()._domain_sale_line_id()
        return domain & Domain([
            '|',
                '|',
                    ('order_partner_id', 'child_of', unquote('partner_id if partner_id else []')),
                    ('order_id.partner_shipping_id', 'child_of', unquote('partner_id if partner_id else []')),
                '|',
                    ('order_partner_id', '=?', unquote('partner_id')),
                    ('order_id.partner_shipping_id', '=?', unquote('partner_id')),
        ])

    sale_order_id = fields.Many2one(related=None, compute='_compute_sale_order_id', inverse=None, store=True, copy=False)
    sale_order_state = fields.Selection(tracking=False)
    sale_line_id = fields.Many2one(tracking=13, copy=False)
    under_warranty = fields.Boolean('Under Warranty', tracking=14)
    quotations_count = fields.Integer('Quotations Count', compute='_compute_quotations_count', export_string_translation=True, groups="sales_team.group_sale_salesman")
    material_line_product_count = fields.Integer(compute='_compute_material_line_product_count', export_string_translation=False)
    pricelist_id = fields.Many2one('product.pricelist', compute="_compute_pricelist_id", export_string_translation=False)
    currency_id = fields.Many2one('res.currency', compute='_compute_currency_id', compute_sql='_compute_currency_id', compute_sudo=True)
    partner_id = fields.Many2one(compute='_compute_partner_id', inverse='_inverse_partner_id', readonly=False, store=True)
    intervention_timesheet_ids = fields.One2many('account.analytic.line', 'planning_slot_id', groups="hr_timesheet.group_hr_timesheet_user", export_string_translation=False)
    intervention_effective_hours = fields.Float(compute='_compute_intervention_effective_hours', compute_sudo=True, export_string_translation=False)
    allow_billable = fields.Boolean(compute='_compute_allow_billable', search='_search_allow_billable', compute_sudo=True, export_string_translation=False)
    allow_timesheets = fields.Boolean(compute='_compute_allow_timesheets', search='_search_allow_timesheets', compute_sudo=True, export_string_translation=False)
    sale_warning_text = fields.Text('Slot Warning', compute='_compute_sale_warning_text', help='Warning for the partner as set by the user.', export_string_translation=False)

    def _get_field_service_field_list(self, field_list):
        self.ensure_one()
        if not field_list:
            return []
        slot_field_list = []
        if self.partner_id and 'partner_id' in field_list:
            slot_field_list.append('partner_id')
        if 'role_id' in field_list:
            slot_field_list.append('role_id')
        return slot_field_list

    def _compute_display_name(self):
        group_by = self.env.context.get('group_by', [])
        field_list = [fname for fname in self._display_name_fields() if fname not in group_by]
        if 'project_id' in field_list and 'partner_id' in field_list:
            for slot in self.sudo():
                slot_field_list = slot._get_field_service_field_list(field_list)
                new_context = {}
                if 'hide_planned_dates' in self.env.context:
                    new_context['hide_planned_dates'] = self.env.context['hide_planned_dates']
                slot.display_name = slot.with_context(new_context)._get_display_name(slot_field_list)
        else:
            super()._compute_display_name()

    @api.depends('sale_line_id')
    def _compute_sale_order_id(self):
        for slot in self:
            if not slot.sale_line_id and slot.state in ['1_draft', '2_published']:
                slot.sale_order_id = False
                continue
            sale_order = slot.sale_order_id
            if slot.sale_line_id and not (sale_order and sale_order == slot.sale_line_id.order_id):
                sale_order = slot.sale_line_id.order_id
            elif sale_order and not slot.sale_line_id:
                consistent_partners = (
                    sale_order.partner_id
                    | sale_order.partner_invoice_id
                    | sale_order.partner_shipping_id
                ).commercial_partner_id
                if not slot.partner_id or slot.partner_id.commercial_partner_id not in consistent_partners:
                    sale_order = False
            slot.sale_order_id = sale_order

    @api.depends('partner_id')
    def _compute_sale_line_id(self):
        super()._compute_sale_line_id()
        for slot in self:
            sale_order = slot.sale_line_id.order_id
            consistent_partners = (
                sale_order.partner_id
                | sale_order.partner_invoice_id
                | sale_order.partner_shipping_id
            ).commercial_partner_id
            if not slot.partner_id or slot.partner_id.commercial_partner_id not in consistent_partners:
                slot.sale_line_id = False

    def _compute_quotations_count(self):
        quotation_data = self.env['sale.order']._read_group([('planning_slot_id', 'in', self.ids)], ['planning_slot_id'], ['__count'])
        mapped_data = {slot.id: count for slot, count in quotation_data}
        for slot in self:
            slot.quotations_count = mapped_data.get(slot.id, 0)

    @api.depends('sale_order_id.order_line.product_uom_qty', 'sale_order_id.order_line.price_total', 'employee_ids.timesheet_product_id')
    def _compute_material_line_product_count(self):
        material_data_sale_order_by_planning_slot = self._get_material_data_sale_order_by_planning_slot()
        for slot in self:
            if self._origin and (sale_order := slot.sale_order_id):
                slot.material_line_product_count = round(material_data_sale_order_by_planning_slot[slot._origin].get(sale_order, {}).get('material_count', 0))
            else:
                slot.material_line_product_count = 0

    @api.depends('sale_order_id.pricelist_id', 'partner_id.property_product_pricelist')
    def _compute_pricelist_id(self):
        pricelist_active = self.env.user.has_group('product.group_product_pricelist')
        for task in self:
            task.pricelist_id = pricelist_active and \
                                (task.sale_order_id.sudo().pricelist_id or task.partner_id.property_product_pricelist)

    @api.depends('pricelist_id', 'company_id')
    def _compute_currency_id(self):
        for task in self:
            task.currency_id = task.pricelist_id.currency_id or task.company_id.currency_id

    def _compute_sql_currency_id(self, table):
        return SQL("COALESCE(%s, %s)", table.pricelist_id.currency_id, table.company_id.currency_id)

    @api.depends('sale_order_id.partner_shipping_id', 'sale_order_id.partner_id')
    def _compute_partner_id(self):
        has_group_delivery_invoice_address = self.env.user.has_group('account.group_delivery_invoice_address')
        for slot in self:
            if slot.sale_order_id:
                slot.partner_id = slot.sale_order_id.partner_shipping_id if has_group_delivery_invoice_address else slot.sale_order_id.partner_id

    def _inverse_partner_id(self):
        for slot in self:
            if sale_order := slot.sale_order_id:
                consistent_partners = (
                    sale_order.partner_id
                    | sale_order.partner_invoice_id
                    | sale_order.partner_shipping_id
                ).commercial_partner_id
                if not slot.partner_id or slot.partner_id.commercial_partner_id not in consistent_partners:
                    slot.sale_order_id = slot.sale_line_id = False

    @api.depends('intervention_timesheet_ids')
    def _compute_intervention_effective_hours(self):
        for slot in self:
            slot.intervention_effective_hours = sum(
                timesheet.unit_amount
                for timesheet in slot.intervention_timesheet_ids
            )

    @api.depends('intervention_timesheet_ids', 'material_line_product_count')
    def _compute_show_customer_preview(self):
        super()._compute_show_customer_preview()

    @api.depends('company_id.planning_project_id')
    def _compute_allow_billable(self):
        for slot in self:
            slot.allow_billable = slot._get_timesheetable_project().allow_billable

    def _search_allow_billable(self, operator, value):
        if operator in Domain.NEGATIVE_OPERATORS:
            return NotImplemented
        return Domain('company_id', 'in', self.env.companies.sudo().filtered_domain([('planning_project_id.allow_billable', operator, value)]).ids)

    @api.depends('company_id.planning_project_id')
    def _compute_allow_timesheets(self):
        for slot in self:
            slot.allow_timesheets = slot._get_timesheetable_project().allow_timesheets

    @api.depends('partner_id.name', 'partner_id.sale_warn_msg')
    def _compute_sale_warning_text(self):
        if not self.env.user.has_group("sale.group_warning_sale"):
            self.sale_warning_text = ""
            return
        for slot in self:
            warnings = OrderedSet()
            if partner_msg := slot.partner_id.sale_warn_msg:
                warnings.add(
                    (slot.partner_id.name or slot.partner_id.display_name) + " - " + partner_msg
                )
            if partner_parent_msg := slot.partner_id.parent_id.sale_warn_msg:
                parent = slot.partner_id.parent_id
                warnings.add((parent.name or parent.display_name) + " - " + partner_parent_msg)
            slot.sale_warning_text = "\n".join(warnings)

    def _search_allow_timesheets(self, operator, value):
        if operator in Domain.NEGATIVE_OPERATORS:
            return NotImplemented
        return Domain('company_id', 'in', self.env.companies.sudo().filtered_domain([('planning_project_id.allow_timesheets', operator, value)]).ids)

    def copy_data(self, default=None):
        vals_list = super().copy_data(default)
        for slot, vals in zip(self, vals_list):
            if slot.state in ['1_draft', '2_published'] and slot.partner_id:
                vals['sale_order_id'] = slot.sale_order_id.id
                vals['sale_line_id'] = slot.sale_line_id.id
        return vals_list

    def write(self, vals):
        res = super().write(vals)
        if 'under_warranty' in vals:
            ongoing_interventions = self.filtered(lambda s: s.state != '4_completed' and s.sale_order_id and not s.sale_order_id.locked)
            lines = ongoing_interventions.sale_order_id.order_line.filtered(lambda l: l.planning_slot_id in ongoing_interventions and l.qty_invoiced == 0)
            if vals['under_warranty']:
                lines.sudo().write({'price_unit': 0, 'technical_price_unit': 0})
            else:
                lines.with_context(force_price_recomputation=True).sudo()._compute_price_unit()
        return res

    def _display_name_fields(self):
        if not self.env.su and self.env.user.has_group('planning.group_planning_user') and not self.env.user.has_group('planning.group_planning_manager'):
            return ['partner_id']
        return super()._display_name_fields()

    def _is_intervention_report_available(self):
        return super()._is_intervention_report_available() or self.material_line_product_count > 0 or self.sudo().intervention_timesheet_ids

    def _get_is_intervention_report_available_domain(self):
        return Domain([
            '|', '|',
            ('under_warranty', '=', False),
            ('sale_order_id', '!=', False),
            ('intervention_timesheet_ids', '!=', False),
        ])

    def _reset_intervention_fields(self):
        self.sale_order_id = False
        self.sale_line_id = False
        super()._reset_intervention_fields()

    def _get_available_product_materials_domain(self):
        self.ensure_one()
        domain = Domain([
            ('company_id', 'in', [self.company_id.id, False]),
            ('sale_ok', '=', True),
            '|', ('type', '=', 'consu'),
                '&', '&',
                    ('type', '=', 'service'),
                    ('invoice_policy', '=', 'delivery'),
                    ('service_type', '=', 'manual'),
        ])
        if travel_product := self.company_id.travel_time_invoicing_product_id.product_variant_id:
            domain &= Domain('id', '!=', travel_product.id)
        return domain

    def _get_fsm_catalog_lines(self, product):
        self.ensure_one()
        lines = self.env['sale.order.line'].sudo().search([
            ('order_id', '=', self.sale_order_id.id),
            ('product_id', '=', product.id),
            ('planning_slot_id', '=', self.id),
        ])
        # `_is_in_section` isn't a searchable field, so it can't be added to the domain above.
        return lines.filtered(lambda sol: sol._is_in_section())

    def _update_fsm_catalog_quantity(self, product, quantity):
        self.ensure_one()
        result = product.set_fsm_quantity(quantity)
        return result, self._get_fsm_catalog_lines(product)

    def _get_material_data_sale_order_by_planning_slot(self):

        def is_material_line(sale_line, slot, employee_mapping_product_ids=None):
            is_not_timesheet_line = True
            if employee_mapping_product_ids:  # Then we need to search the product in the employee mappings
                is_not_timesheet_line = sale_line.product_id.id not in employee_mapping_product_ids
            is_not_empty = sale_line.product_uom_qty != 0
            is_not_service_from_so = sale_line != slot.sale_line_id
            is_task_related = (slot or slot._origin) == sale_line.planning_slot_id
            return all([is_not_timesheet_line, is_not_empty, is_not_service_from_so, is_task_related])

        service_products = (
            self.employee_ids.sudo().timesheet_product_id
            | self.env.ref('sale_timesheet.time_product')
            | self.company_id.travel_time_invoicing_product_id.product_variant_id
        )
        sol_read_group = self.env['sale.order.line'].sudo()._read_group(
            [
                ('order_id', 'in', self.sale_order_id.ids),
                ('product_id', 'not in', service_products.ids),
                ('product_uom_qty', '>', 0),
                ('planning_slot_id', 'in', self.ids),
            ],
            ['planning_slot_id', 'order_id', 'id'], ['product_uom_qty:sum'],
        )
        material_data_sale_order_by_planning_slot = defaultdict(dict)
        for slot, order, sol, material_count in sol_read_group:
            material_data_sale_order_by_planning_slot.setdefault(slot, {}).setdefault(order, {'material_count': 0, 'material_sale_lines': self.env['sale.order.line']})
            material_data_sale_order_by_planning_slot[slot][order]['material_count'] += material_count
            material_data_sale_order_by_planning_slot[slot][order]['material_sale_lines'] |= sol
        return material_data_sale_order_by_planning_slot

    def action_view_material(self):
        if not self.partner_id:
            raise UserError(self.env._('A customer should be set to be able to add materials to this intervention.'))
        self_with_company = self.with_company(self.company_id)
        order_sudo = self_with_company.sale_order_id.sudo()
        domain = self_with_company._get_available_product_materials_domain()
        context = {
            'create': self.env['product.template'].has_access('create'),
            'intervention_id': self.id,  # avoid 'default_' context key as we are going to create SOL with this context
            'pricelist': self_with_company.partner_id.property_product_pricelist.id,
            'order_id': order_sudo.id,
            **order_sudo.sudo().with_context(child_field='order_line')._get_action_add_from_catalog_extra_context(),
            'default_invoice_policy': 'delivery',
            'search_default_fsm_quantity': self.state == '4_completed',
            'child_field': 'order_line',
        }
        if not context['product_catalog_currency_id']:
            # fallback currency in case no SO yet
            context['product_catalog_currency_id'] = self.currency_id.id

        action = self.env['ir.actions.act_window']._for_xml_id('planning_field_service_sale_timesheet.action_product_catalog')
        action.update({
            'domain': domain,
            'context': context,
        })
        return action

    def _get_action_quotation_context(self):
        return {
            'default_project_id': self._get_timesheetable_project().id,
            'default_partner_id': self.partner_id.id,
            'default_user_id': self.env.uid,
            'default_planning_slot_id': self.id,
            'default_company_id': self.company_id.id,
            'default_origin': self.env._(
                "Onsite meeting on %(date)s",
                date=format_date(self.env, self.start_datetime)
            ),
        }

    def action_new_quotation(self):
        view_form_id = self.env.ref('sale.view_order_form').id
        action = self.env["ir.actions.actions"]._for_xml_id("sale.action_quotations")
        action.update({
            'views': [(view_form_id, 'form')],
            'view_mode': 'form',
            'name': self.name,
            'context': self._get_action_quotation_context(),
        })
        return action

    def action_view_quotations(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("sale.action_quotations")
        domain = [('planning_slot_id', '=', self.id)]
        action.update({
            'name': self.name,
            'domain': domain,
            'context': self._get_action_quotation_context(),
        })
        if self.quotations_count == 1:
            action['res_id'] = self.env['sale.order'].search(domain).id
            views = [(view_id, view_type) for view_id, view_type in action['views'] if view_type == 'form']
            if not views:
                views = [(self.env.ref('sale.view_order_form').id, 'form')]
            action['views'] = views
        return action

    def _action_complete(self, from_status_bar=False):
        self.ensure_one()
        super()._action_complete(from_status_bar)
        if self.env.company.field_service_travel_fees and not self.under_warranty:
            self._generate_travel_sol()
        project = self._get_timesheetable_project()
        if (
            (
                self.material_line_product_count
                and self.env['res.groups']._is_feature_enabled('planning.group_field_service_allow_material')
            )
            or (project.sudo().allow_timesheets and (not self.under_warranty and project.sudo().allow_billable))
        ):
            self._ensure_sale_order_set()
        timesheets = self.env['account.analytic.line']
        if project.sudo().allow_timesheets:
            timesheets = self.sudo()._generate_timesheets()
            self.sudo()._generate_service_sale_order_lines(timesheets)
        if self.sale_order_id.sudo().state in ['draft', 'sent']:
            self.sale_order_id.sudo().action_confirm()
        self.sudo()._prepare_materials_delivery(timesheets)

    def _ensure_sale_order_set(self):
        self.ensure_one()
        if not self.sale_order_id:
            self._generate_sale_order()
        sale_order = self.sale_order_id
        if self.env.user.has_group('planning.group_planning_user'):
            sale_order = self.sale_order_id.sudo()
        if not sale_order.project_id:
            sale_order.project_id = self._get_timesheetable_project()
        return self.sale_order_id

    def _prepare_sale_order_values(self):
        team = None
        if 'crm.team' in self.env:
            team = self.env['crm.team'].sudo()._get_default_team_id(user_id=self.user_ids[:1].id, domain=None)
        project = self._get_timesheetable_project()
        vals = {
            'partner_id': self.partner_id.id,
            'company_id': self.company_id.id or self.partner_id.company_id.id or self.env.company.id,
            'project_id': project.id,
            'team_id': team.id if team else False,
            'origin': self.env._("%(project_name)s - Field Service - %(intervention_date)s", project_name=project.name, intervention_date=format_date(self.env, self.start_datetime)),
        }
        return vals

    def _generate_sale_order(self):
        """ Create the SO from the task, with the 'service product' sales line and link all timesheet to that line it """
        self.ensure_one()
        if not self.partner_id:
            raise UserError(self.env._('A customer should be set on the intervention to generate a worksheet.'))
        SaleOrder = self.env['sale.order']
        if self.env.user.has_group('planning.group_planning_user'):
            SaleOrder = SaleOrder.sudo()
        user = next((u for u in (self.user_ids + self.env.user) if u.has_group('sales_team.group_sale_salesman') or u.has_group('account.group_account_invoice')), self.env['res.users'])
        vals = self._prepare_sale_order_values()
        sale_order = SaleOrder.create(vals)
        # update after creation since onchange_partner_id sets the current user
        if user:
            sale_order.user_id = user
        else:
            sale_order.user_id = False
        self.sale_order_id = sale_order

    def _get_timesheet_vals(self, additional_vals=None):
        self.ensure_one()
        return {
            'project_id': self._get_timesheetable_project().id,
            'planning_slot_id': self.id,
            'unit_amount': self.allocated_hours,
            'date': self.start_datetime.date(),
            'name': self.env._('Field service intervention'),
            **(additional_vals or {}),
        }

    def _generate_timesheets(self):
        timesheet_vals_list = []
        minimum_duration = self.env['ir.config_parameter'].sudo().get_int('timesheet_grid.timesheet_min_duration', 15)
        rounding = self.env['ir.config_parameter'].sudo().get_int('timesheet_grid.timesheet_rounding', 15)
        for slot in self:
            if slot._get_timesheetable_project().sudo().allow_timesheets:
                allocated_minutes = slot.allocated_hours * 60.0
                minutes_spent = allocated_minutes / len(slot.employee_ids) if slot.employee_ids else allocated_minutes
                for employee in slot.employee_ids:
                    timesheet_vals_list.append(slot._get_timesheet_vals({
                        'employee_id': employee.id,
                        'unit_amount': round_time_spent(minutes_spent, minimum_duration, rounding) / 60.0,
                    }))
        return self.env['account.analytic.line'].create(timesheet_vals_list)

    def _get_timesheetable_project(self):
        self.ensure_one()
        return self.company_id.planning_project_id

    def _get_sale_order_line_vals(self):
        self.ensure_one()
        return {
            'order_id': self.sale_order_id.id,
            # The project is given to prevent the SOL to create a new project or task based on the config of the product.
            'project_id': self._get_timesheetable_project().id,
            'planning_slot_id': self.id,
        }

    def _generate_service_sale_order_lines(self, timesheets):
        self.ensure_one()
        sale_order_lines = self.env['sale.order.line']
        if not (timesheets and self.sale_order_id and self._get_timesheetable_project().allow_billable):
            return sale_order_lines

        def convert_unit_amount_based_on_uom(product, timesheet):
            if timesheet.product_uom_id != product.uom_id:
                return timesheet.product_uom_id._compute_quantity(timesheet.unit_amount, product.uom_id, rounding_method='HALF-UP')
            else:
                return timesheet.unit_amount

        timesheets_per_product = defaultdict(self.env['account.analytic.line'].browse)
        default_timesheet_product = self.sale_line_id.product_id or self.env.ref('sale_timesheet.time_product')
        existing_sols_sudo = self.sale_order_id.sudo().order_line if self.sale_line_id else self.env['sale.order.line']
        for employee, analytic_lines in timesheets.grouped('employee_id').items():
            timesheet_product = employee.sudo().timesheet_product_id or default_timesheet_product
            if timesheet_product not in existing_sols_sudo.product_id:
                timesheets_per_product[timesheet_product] += analytic_lines
        if timesheets_per_product and not self.under_warranty:
            sol_vals_list = [
                {
                    **self._get_sale_order_line_vals(),
                    'product_id': product.id,
                    'product_uom_qty': sum(convert_unit_amount_based_on_uom(product, timesheet) for timesheet in timesheets),
                }
                for product, timesheets in timesheets_per_product.items()
            ]
            if sol_vals_list:
                sale_order_lines = self.env['sale.order.line'].create(sol_vals_list)
                sols_per_product = sale_order_lines.grouped('product_id')
                for product, sol in sols_per_product.items():
                    timesheets = timesheets_per_product[product]
                    timesheets.write({
                        'so_line': sol.id,
                        'is_so_line_edited': True,
                    })
                self.sale_line_id = sols_per_product.get(default_timesheet_product, next(iter(sale_order_lines)))

        elif self.sale_line_id:
            self.sale_line_id.qty_delivered = sum(convert_unit_amount_based_on_uom(self.sale_line_id.product_id, timesheet) for timesheet in timesheets)
            timesheets.write({
                'so_line': self.sale_line_id.id,
                'is_so_line_edited': True,
            })
            if self.under_warranty:
                self.sale_line_id.price_unit = 0

        return sale_order_lines

    def _prepare_materials_delivery(self, timesheets):
        # While planning_field_service_sale_stock is not installed then we automatically deliver materials
        sale_order_lines = self.env['sale.order.line'].sudo().search([
            ('id', 'not in', timesheets.so_line.ids),
            ('planning_slot_id', 'in', self.ids),
            ('order_id', 'in', self.sale_order_id.sudo().filtered(lambda so: so.state == 'sale').ids),
        ])
        if self.under_warranty:
            sale_order_lines.price_unit = 0
        for sol in sale_order_lines:
            # if a SOL with service product that has invoicing policy based on milestones,
            # the delivered quantity will be computed based on the milestones reached
            if sol.product_id.service_policy != 'delivered_milestones':
                sol.qty_delivered = sol.product_uom_qty

    def _has_no_billable_products(self):
        return all(sol.price_unit == 0 for sol in self.sale_order_id.order_line)

    def action_open_timesheets(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('hr_timesheet.timesheet_action_all')
        # Remove all references to the original action, to avoid studio and be able to change the action name
        action.pop('id', None)
        action.pop('xml_id', None)
        action.pop('display_name', None)
        action.update({
            'name': self.env._("Timesheets"),
            'domain': [('planning_slot_id', '=', self.id)],
            'context': {
                'default_planning_slot_id': self.id,
                'default_project_id': self._get_timesheetable_project().id,
                'default_employee_id': self.employee_ids[:1].id,
                'default_date': self.start_datetime.date(),
                'grid_anchor': self.start_datetime.date(),
            },
        })
        return action

    def _get_travel_fee_quantity(self):
        self.ensure_one()
        if self.company_id.field_service_travel_fees_mode != 'distance':
            return 1

        work_locations = self.resource_ids.sudo()._get_work_location()
        work_location = work_locations if len(work_locations) == 1 else self.company_id.partner_id
        customer_location = self.partner_id
        missing_location_message = self.env._(
            "Travel time couldn't be invoiced because the customer's or technician's work address couldn't be located."
        )
        odoobot = self.env.ref('base.partner_root')
        for partner in (work_location, customer_location):
            if not partner._ensure_geolocalized():
                self.message_post(
                    body=missing_location_message,
                    author_id=odoobot.id,
                    subtype_xmlid='mail.mt_note',
                )
                return False

        travel_info = work_location._get_travel_information_between_partners(customer_location)
        if not travel_info or travel_info.get('error'):
            reason = (travel_info or {}).get('error') or self.env._("Mapbox could not be reached")
            self.message_post(
                body=self.env._("Travel time couldn't be invoiced because %(reason)s.", reason=reason),
                author_id=odoobot.id,
                subtype_xmlid='mail.mt_note',
            )
            return False
        return float_round(travel_info['distance'], precision_digits=0, rounding_method='UP')

    def _generate_travel_sol(self):
        self.ensure_one()
        if self.company_id.field_service_travel_fees and (quantity := self._get_travel_fee_quantity()):
            self._ensure_sale_order_set()
            product = self.company_id.travel_time_invoicing_product_id.product_variant_id
            self.env["sale.order.line"].sudo().create({
                **self._get_sale_order_line_vals(),
                'product_id': product.id,
                'product_uom_qty': quantity,
                'price_unit': product._get_tax_included_unit_price(
                    self.sale_order_id.company_id,
                    self.sale_order_id.currency_id,
                    self.sale_order_id.date_order,
                    'sale',
                    fiscal_position=self.sale_order_id.fiscal_position_id,
                ),
            })

    def action_plan_shift(self):
        action = super().action_plan_shift()
        if self.under_warranty:
            action["context"]["default_under_warranty"] = self.under_warranty
        return action
