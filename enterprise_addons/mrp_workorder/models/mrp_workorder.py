# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from ast import literal_eval
from bisect import bisect_left
from collections import defaultdict
from datetime import datetime, timedelta, UTC

from dateutil.relativedelta import relativedelta

from odoo import Command, api, fields, models, _
from odoo.fields import Domain
from odoo.addons.web.controllers.utils import clean_action
from odoo.exceptions import UserError, ValidationError, RedirectWarning
from odoo.tools import float_compare
from odoo.tools.intervals import Intervals
from odoo.tools.date_utils import sum_intervals
from odoo.http import request


class MrpWorkorder(models.Model):
    _name = 'mrp.workorder'
    _inherit = ['hr.mixin', 'mrp.workorder']

    quality_point_ids = fields.Many2many('quality.point', compute='_compute_quality_point_ids', store=True)
    quality_point_count = fields.Integer('Steps', compute='_compute_quality_point_count')

    check_ids = fields.One2many('quality.check', 'workorder_id')
    finished_product_check_ids = fields.Many2many('quality.check', compute='_compute_finished_product_check_ids')
    done_check_ids = fields.Many2many('quality.check', compute='_compute_done_check_ids')
    quality_check_todo = fields.Boolean(compute='_compute_check')
    quality_check_fail = fields.Boolean(compute='_compute_check')
    quality_alert_ids = fields.One2many('quality.alert', 'workorder_id')
    quality_alert_count = fields.Integer(compute="_compute_quality_alert_count")

    current_quality_check_id = fields.Many2one(
        'quality.check', "Current Quality Check", check_company=True, index=True)

    # QC-related fields
    allow_producing_quantity_change = fields.Boolean('Allow Changes to Producing Quantity', default=True)

    is_last_lot = fields.Boolean('Is Last lot', compute='_compute_is_last_lot')
    is_first_started_wo = fields.Boolean('Is The first Work Order', compute='_compute_is_last_unfinished_wo')
    is_last_unfinished_wo = fields.Boolean('Is Last Work Order To Process', compute='_compute_is_last_unfinished_wo', store=False)
    move_id = fields.Many2one(related='current_quality_check_id.move_id', readonly=False)
    move_line_ids = fields.One2many(related='move_id.move_line_ids')
    quality_state = fields.Selection(related='current_quality_check_id.quality_state', string="Quality State", readonly=False)
    test_type_id = fields.Many2one('quality.point.test_type', 'Test Type', related='current_quality_check_id.test_type_id')
    test_type = fields.Char(related='test_type_id.technical_name')
    user_id = fields.Many2one(related='current_quality_check_id.user_id', readonly=False)
    worksheet_page = fields.Integer('Worksheet page')
    picture = fields.Binary(related='current_quality_check_id.picture', readonly=False)
    product_description_variants = fields.Char(related='production_id.product_description_variants')

    # used to display the connected employee that will start a workorder on the tablet view
    employee_id = fields.Many2one('hr.employee', string="Employee", compute='_compute_employee_id')
    employee_name = fields.Char(compute='_compute_employee_id')

    # employees that started working on the wo
    employee_ids = fields.Many2many('hr.employee', bypass_search_access=True, string='Working employees', copy=False)
    # employees assigned to the wo
    employee_assigned_ids = fields.Many2many('hr.employee', 'mrp_workorder_employee_assigned',
                                             'workorder_id', 'employee_id', string='Assigned', tracking=True, falsy_value_label='Unassigned Work Orders',
                                             domain="[('company_id', 'in', allowed_company_ids)]")

    # list of employees allowed to work on the workcenter
    allowed_employees = fields.Many2many(related='workcenter_id.employee_ids')
    # True if all employees are allowed on that workcenter
    all_employees_allowed = fields.Boolean(compute='_all_employees_allowed')

    # Technical field to store the estimated hourly cost of employee at time of work order completion (i.e. to keep a consistent cost).
    employee_costs_hour = fields.Float(string='Employee Cost per hour', default=0.0)

    @api.depends('operation_id')
    def _compute_quality_point_ids(self):
        for workorder in self:
            quality_points = workorder.operation_id.quality_point_ids
            quality_points = quality_points.filtered(lambda qp: (not qp.product_ids or workorder.production_id.product_id in qp.product_ids) and (qp.company_id == workorder.company_id))
            workorder.quality_point_ids = quality_points

    @api.depends('operation_id')
    def _compute_quality_point_count(self):
        for workorder in self:
            quality_point = workorder.operation_id.quality_point_ids
            workorder.quality_point_count = len(quality_point)

    @api.depends('qty_producing', 'qty_remaining')
    def _compute_is_last_lot(self):
        for wo in self:
            wo.is_last_lot = wo.production_id.uom_id.compare(wo.qty_producing, wo.qty_remaining) >= 0

    @api.depends('production_id.workorder_ids')
    def _compute_is_last_unfinished_wo(self):
        for wo in self:
            wo.is_first_started_wo = all(wo.state != 'done' for wo in (wo.production_id.workorder_ids - wo))
            other_wos = wo.production_id.workorder_ids - wo
            other_states = other_wos.mapped(lambda w: w.state in ['done', 'cancel'])
            wo.is_last_unfinished_wo = all(other_states)

    @api.depends('check_ids')
    def _compute_finished_product_check_ids(self):
        for wo in self:
            wo.finished_product_check_ids = wo.check_ids.filtered(lambda c: c.finished_product_sequence == wo.qty_produced)

    @api.depends('check_ids.quality_state')
    def _compute_done_check_ids(self):
        for wo in self:
            wo.done_check_ids = wo.check_ids.filtered(lambda c: c.quality_state != 'none')

    @api.depends('time_ids.total_cost')
    def _compute_cost(self):
        super()._compute_cost()

    def unlink(self):
        self.check_ids.sudo().unlink()
        return super().unlink()

    def action_back(self):
        self.ensure_one()
        if self._should_be_pending():
            self.button_pending()
        domain = [('state', 'not in', ['done', 'cancel', 'blocked'])]
        if self.env.context.get('from_manufacturing_order'):
            # from workorder on MO
            action = self.env["ir.actions.actions"]._for_xml_id("mrp_workorder.mrp_workorder_action_tablet")
            action['domain'] = domain
            action['context'] = literal_eval(action['context']) | {
                'no_breadcrumbs': True,
                'search_default_production_id': self.production_id.id,
                'search_default_workcenter_id': False,
                'search_default_progress': False,
                'search_default_ready': False,
                'from_manufacturing_order': True,
            }
        elif self.env.context.get('mrp_display') or self.env.context.get('check_create_backorder'):
            return
        else:
            # from workcenter kanban view
            action = self.env["ir.actions.actions"]._for_xml_id("mrp_workorder.mrp_workorder_action_tablet")
            action['domain'] = domain
            action['context'] = literal_eval(action['context'].replace('active_id', str(self.id))) | {
                'no_breadcrumbs': True,
                'search_default_workcenter_id': self.workcenter_id.id,
            }
        if self.employee_id:
            action['context']['employee_id'] = self.employee_id.id
            action['context']['employee_name'] = self.employee_id.name
        if self.employee_ids:
            action['context']['employee_ids'] = self.employee_ids
        return clean_action(action, self.env)

    def action_cancel(self):
        self.mapped('check_ids').sudo().unlink()
        return super().action_cancel()

    def action_generate_serial(self):
        self.ensure_one()
        return self.production_id.action_generate_serial(self)

    def _change_quality_check(self, position):
        """Change the quality check currently set on the workorder `self`.

        The workorder points to a check. A check belongs to a chain.
        This method allows to change the selected check by moving on the checks
        chain according to `position`.

        :param position: Where we need to change the cursor on the check chain
        :type position: string
        """
        self.ensure_one()
        assert position in ['first', 'next', 'previous', 'last']
        checks_to_consider = self.check_ids.filtered(lambda c: c.quality_state == 'none')
        if position == 'first':
            check = checks_to_consider.filtered(lambda check: not check.previous_check_id)
        elif position == 'next':
            check = self.current_quality_check_id.next_check_id
            if not check:
                check = checks_to_consider[:1]
            elif check.quality_state != 'none':
                self.current_quality_check_id = check
                return self._change_quality_check(position='next')
        elif position == 'previous':
            check = self.current_quality_check_id.previous_check_id
        else:
            check = checks_to_consider.filtered(lambda check: not check.next_check_id)
        self.write({
            'allow_producing_quantity_change':
                not check.previous_check_id.filtered(lambda c: c.quality_state != 'fail')
                and all(c.quality_state != 'fail' for c in checks_to_consider)
                and self.is_first_started_wo,
            'current_quality_check_id': check.id,
        })
        return check.id

    def action_add_component(self):
        self.ensure_one()
        return self.production_id.with_context(workorder_id=self.id).action_add_component()

    def action_add_byproduct(self):
        self.ensure_one()
        return self.production_id.with_context(workorder_id=self.id).action_add_byproduct()

    def action_add_workorder(self):
        self.ensure_one()
        default_blocking_wo_id = self.id
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mrp_production.additional.workorder',
            'views': [[self.env.ref('mrp_workorder.view_mrp_production_additional_workorder_wizard').id, 'form']],
            'name': _('Add Work Order'),
            'target': 'new',
            'context': {
                'default_production_id': self.production_id.id,
                'default_blocked_by_workorder_id': default_blocking_wo_id,
            }
        }

    def button_start(self, raise_on_invalid_state=False, bypass=False):
        skip_employee_check = bypass or (not request and not self.env.user.employee_id)
        main_employee = False
        if not skip_employee_check:
            if not self.env.context.get('mrp_display'):
                main_employee = self.env.user.employee_id.id
                if not self.env.user.employee_id:
                    if self.env.user.has_group('hr.group_hr_user'):
                        raise RedirectWarning(
                            message=_("You need to link this user to an employee of this company to process the work order."),
                            action={
                                'name': _("Create Employee"),
                                'type': 'ir.actions.act_window',
                                'res_model': 'hr.employee',
                                'views': [[False, 'form']],
                                'target': 'new',
                                'context': {'default_user_id': self.env.user.id},
                            },
                            button_text=_("Create Employee"),
                        )
                    else:
                        raise UserError(_("You need to link this user to an employee of this company to process the work order."))
            else:
                connected_employees = self.env['hr.employee'].get_employees_connected()
                if len(connected_employees) == 0:
                    raise UserError(_("You need to log in to process this work order."))
                main_employee = self.env['hr.employee'].get_session_owner()
                if not main_employee:
                    raise UserError(_("There is no session chief. Please log in."))
            if any(main_employee not in [emp.id for emp in wo.allowed_employees] and not wo.all_employees_allowed for wo in self):
                raise UserError(_("You are not allowed to work on the workorder"))

        res = super().button_start(raise_on_invalid_state=raise_on_invalid_state)

        if main_employee:
            main_employee = self.env['hr.employee'].browse(main_employee)
            for wo in self:
                if (len(wo.allowed_employees) == 0 or main_employee in wo.allowed_employees) and wo.state not in ('done', 'cancel'):
                    wo.start_employee(main_employee.id)
                    wo.employee_ids |= main_employee
                    wo.employee_assigned_ids |= main_employee

        return res

    def button_finish(self):
        """ When using the Done button of the simplified view, validate directly some types of quality checks
        """
        for workorder in self:
            if workorder.state in ('done', 'cancel'):
                continue
            workorder.employee_costs_hour = workorder.workcenter_id.employee_costs_hour
        self.verify_quality_checks()
        return super().button_finish()

    def verify_quality_checks(self):
        for check in self.check_ids:
            if check.quality_state in ['pass', 'fail']:
                continue
            if check.test_type in ['register_consumed_materials', 'register_byproducts', 'instructions']:
                check.quality_state = 'pass'
            else:
                raise UserError(_("You need to complete Quality Checks using the Shop Floor before marking Work Order as Done."))

    def action_propose_change(self, change_type, check_id):
        change_type_to_title = {'update_step': 'Update Instructions', 'remove_step': 'Remove Step', 'set_picture': 'Add a Picture'}
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'propose.change',
            'views': [[self.env.ref('mrp_workorder.view_propose_change_wizard').id, 'form']],
            'name': change_type_to_title[change_type],
            'target': 'new',
            'context': {
                'default_workorder_id': self.id,
                'default_step_id': check_id,
                'default_change_type': change_type,
            }
        }

    def action_add_step(self):
        self.ensure_one()
        if self.current_quality_check_id:
            team = self.current_quality_check_id.team_id
        else:
            team = self.env['quality.alert.team'].search(['|', ('company_id', '=', self.company_id.id), ('company_id', '=', False)], limit=1)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'quality.check',
            'views': [[self.env.ref('mrp_workorder.add_quality_check_from_tablet').id, 'form']],
            'name': _('Add a Step'),
            'target': 'new',
            'context': {
                'default_test_type_id': self.env.ref('quality.test_type_instructions').id,
                'default_workorder_id': self.id,
                'default_production_id': self.production_id.id,
                'default_product_id': self.product_id.id,
                'default_team_id': team.id,
            }
        }

    def action_open_mes(self):
        action = self.env['ir.actions.actions']._for_xml_id('mrp_workorder.action_mrp_display')
        action['context'] = literal_eval(action['context']) | {
            'workcenter_id': self.workcenter_id.id,
            'search_default_progress': False,
            'search_default_ready': False,
            'search_default_name': self.production_id.name,
            'shouldHideNewWorkcenterButton': True,
        }
        del action['context']['search_default_filter_ready']  # Remove MO Ready
        return action

    def action_log_note(self):
        return self.production_id.action_log_note()

    def _compute_check(self):
        for workorder in self:
            todo = False
            fail = False
            for check in workorder.check_ids:
                if check.quality_state == 'none':
                    todo = True
                elif check.quality_state == 'fail':
                    fail = True
                if fail and todo:
                    break
            workorder.quality_check_fail = fail
            workorder.quality_check_todo = todo

    def _compute_quality_alert_count(self):
        for workorder in self:
            workorder.quality_alert_count = len(workorder.quality_alert_ids)

    def _create_checks(self):
        for wo in self:
            # Track components which have a control point
            processed_move = self.env['stock.move']

            production = wo.production_id

            move_raw_ids = wo.move_raw_ids.filtered(lambda m: m.state not in ('done', 'cancel'))
            move_finished_ids = wo.move_finished_ids.filtered(lambda m: m.state not in ('done', 'cancel') and m.product_id != wo.production_id.product_id)
            previous_check = self.env['quality.check']
            for point in wo.quality_point_ids:
                # Check if we need a quality control for this point
                if point.check_execute_now():
                    moves = self.env['stock.move']
                    values = {
                        'production_id': production.id,
                        'workorder_id': wo.id,
                        'point_id': point.id,
                        'team_id': point.team_id.id,
                        'company_id': wo.company_id.id,
                        'product_id': production.product_id.id,
                        # Two steps are from the same production
                        # if and only if the produced quantities at the time they were created are equal.
                        'finished_product_sequence': wo.qty_produced,
                        'previous_check_id': previous_check.id,
                        'worksheet_document': point.worksheet_document,
                    }
                    if point.test_type == 'register_byproducts':
                        moves = move_finished_ids.filtered(lambda m: m.byproduct_id == point.byproduct_id)
                        if not moves:
                            moves = production.move_finished_ids.filtered(lambda m: not m.operation_id and m.byproduct_id == point.byproduct_id)
                    elif point.test_type == 'register_consumed_materials':
                        moves = move_raw_ids.filtered(lambda m: m.bom_line_id == point.bom_line_id)
                        if not moves:
                            moves = production.move_raw_ids.filtered(lambda m: not m.operation_id and m.bom_line_id == point.bom_line_id)
                    else:
                        check = self.env['quality.check'].create(values)
                        previous_check.next_check_id = check
                        previous_check = check
                    # Create 'register ...' checks
                    for move in moves:
                        check_vals = values.copy()
                        # Create quality check and link it to the chain
                        check_vals.update({
                            'previous_check_id': previous_check.id,
                            'move_id': move.id,
                        })
                        check = self.env['quality.check'].create(check_vals)
                        previous_check.next_check_id = check
                        previous_check = check
                    processed_move |= moves

            # Set default quality_check
            wo._change_quality_check(position='first')

    def pre_record_production(self):
        self.ensure_one()
        self._check_company()
        if any(x.quality_state == 'none' for x in self.check_ids if x.test_type != 'instructions'):
            raise UserError(_('You still need to do the quality checks!'))
        if self.uom_id.compare(self.qty_producing, 0) <= 0 and not self.production_bom_id.continuous:
            raise UserError(_('Please set the quantity you are currently producing. It should be different from zero.'))

    def record_production(self):
        if not self:
            return True

        self.pre_record_production()

        backorder = False
        # Trigger the backorder process if we produce less than expected
        if self.uom_id.compare(self.qty_producing, self.qty_to_produce) == -1 and self.is_first_started_wo \
            and not self.production_bom_id.continuous:
            match self.production_id.picking_type_id.create_backorder:
                case "ask":
                    return self.production_id.with_context(workorder_id_to_finish=self.id)._action_generate_backorder_wizard(self.production_id)
                case "always":
                    backorder = self.production_id._split_productions({self.production_id: [self.qty_producing, self.qty_remaining - self.qty_producing]})[1:]
                    for workorder in backorder.workorder_ids:
                        if not self.env.context.get('no_start_next', False):
                            workorder.qty_producing = workorder.qty_remaining
                    self.production_id.product_qty = self.qty_producing

        else:
            if self.operation_id:
                backorder = (self.production_id.production_group_id.production_ids - self.production_id).filtered(
                    lambda p: p.workorder_ids.filtered(lambda wo: wo.operation_id == self.operation_id).state not in ('cancel', 'done')
                )[:1]
            else:
                index = list(self.production_id.workorder_ids).index(self)
                backorder = (self.production_id.production_group_id.production_ids - self.production_id).filtered(
                    lambda p: index < len(p.workorder_ids) and p.workorder_ids[index].state not in ('cancel', 'done')
                )[:1]

        return self.post_record_production(backorder)

    def post_record_production(self, backorders=False):

        self.button_finish()

        if backorders:
            for wo in (self.production_id | backorders).workorder_ids:
                if wo.state in ('done', 'cancel'):
                    continue
                wo.current_quality_check_id.move_id = wo.move_id

        return self.action_back()

    # --------------------------
    # Buttons from quality.check
    # --------------------------

    def action_open_manufacturing_order(self):
        no_start_next = self.env.context.get("no_start_next", True)
        action = self.with_context(no_start_next=no_start_next).do_finish()
        try:
            with self.env.cr.savepoint():
                res = self.production_id.button_mark_done()
                if res is not True:
                    res['context'] = dict(res.get('context', {}), from_workorder=True)
                    return res
        except (UserError, ValidationError) as e:
            # log next activity on MO with error message
            self.production_id.activity_schedule(
                'mail.mail_activity_data_warning',
                note=str(e),
                summary=('The %s could not be closed') % (self.production_id.name),
                user_id=self.env.user.id)
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'mrp.production',
                'views': [[self.env.ref('mrp.mrp_production_form_view').id, 'form']],
                'res_id': self.production_id.id,
                'target': 'main',
            }
        return action

    def do_finish(self):
        for wo in self:
            if wo.state == 'ready' and not wo.qty_produced:
                wo.qty_produced = wo.qty_to_produce
                if not wo.production_bom_id.continuous:
                    wo.qty_producing = wo.qty_to_produce
        self.end_all()
        if self.state != 'done':
            loss_id = self.env['mrp.workcenter.productivity.loss'].search([('loss_type', '=', 'productive')], limit=1)
            if len(loss_id) < 1:
                raise UserError(_("You need to define at least one productivity loss in the category 'Productive'. Create one from the Manufacturing app, menu: Configuration / Productivity Losses."))
            action = self.record_production()
            self._set_default_time_log(loss_id)
            if action is not True:
                return action
        # workorder list view action should redirect to the same view instead of workorder kanban view when WO mark as done.
        return self.action_back()

    def get_summary_data(self):
        self.ensure_one()
        # show rainbow man only the first time
        show_rainbow = any(not t.date_end for t in self.time_ids)
        self.end_all()
        if any(step.quality_state == 'none' for step in self.check_ids):
            raise UserError(_('You still need to do the quality checks!'))
        last30op = self.env['mrp.workorder'].search_read([
            ('operation_id', '=', self.operation_id.id),
            ('state', '=', 'done'),
            ('date_finished', '>', fields.Date.context_today(self) - relativedelta(days=30)),
        ], ['duration', 'qty_produced'])
        last30op = sorted([item['duration'] / item['qty_produced'] for item in last30op])
        # show rainbow man only for the best time in the last 30 days.
        if last30op:
            show_rainbow = show_rainbow and float_compare((self.duration / self.qty_producing), last30op[0], precision_digits=2) <= 0

        score = 3
        if self.check_ids:
            passed_checks = len([check for check in self.check_ids if check.quality_state == 'pass'])
            score = int(3.0 * passed_checks / len(self.check_ids))

        return {
            'duration': self.duration,
            'position': bisect_left(last30op, self.duration), # which position regarded other workorders ranked by duration
            'quality_score': score,
            'show_rainbow': show_rainbow,
        }

    def _action_confirm(self):
        res = super()._action_confirm()
        self.filtered(lambda wo: wo.state != 'cancel' and not wo.check_ids)._create_checks()
        return res

    def _update_qty_producing(self, quantity):
        if self.uom_id.is_zero(quantity):
            self.check_ids.unlink()
        super()._update_qty_producing(quantity)

    def _web_gantt_reschedule_is_record_candidate(self, start_date_field_name, stop_date_field_name):
        return self.state not in ['progress', 'done', 'cancel'] \
            and super()._web_gantt_reschedule_is_record_candidate(start_date_field_name, stop_date_field_name)

    def _web_gantt_reschedule_compute_dates(self, date_candidate, search_forward, start_date_field_name, stop_date_field_name):
        from_date, to_date = self.workcenter_id._get_first_available_slot(date_candidate, self.duration_expected, forward=search_forward, leaves_to_ignore=self.leave_id)
        return [from_date, to_date]

    def _web_gantt_reschedule_write_new_dates(self, new_start_date, new_stop_date, start_date_field_name, stop_date_field_name):
        return super(MrpWorkorder, self.with_context(bypass_duration_calculation=True))._web_gantt_reschedule_write_new_dates(new_start_date, new_stop_date, start_date_field_name, stop_date_field_name)

    def _web_gantt_progress_bar_workcenter_id(self, res_ids, start, stop):
        self.env['mrp.workorder'].check_access('read')
        workcenters = self.env['mrp.workcenter'].search([('id', 'in', res_ids)])
        workorders = self.env['mrp.workorder'].search([
            ('workcenter_id', 'in', res_ids),
            ('state', 'not in', ['done', 'cancel']),
            ('date_start', '<=', stop.replace(tzinfo=None)),
            ('date_finished', '>=', start.replace(tzinfo=None)),
        ])
        planned_hours = defaultdict(float)
        workcenters_work_intervals, dummy = workcenters.resource_id._get_valid_work_intervals(start, stop)
        for workorder in workorders:
            max_start = max(start, workorder.date_start.replace(tzinfo=UTC))
            min_finished = min(stop, workorder.date_finished.replace(tzinfo=UTC))
            interval = Intervals([(max_start, min_finished, self.env['resource.calendar.attendance'])])
            work_intervals = interval & workcenters_work_intervals[workorder.workcenter_id.resource_id.id]
            planned_hours[workorder.workcenter_id] += sum_intervals(work_intervals)
        work_hours = {
            id: sum_intervals(work_intervals) for id, work_intervals in workcenters_work_intervals.items()
        }
        return {
            workcenter.id: {
                'value': planned_hours[workcenter],
                'max_value': work_hours.get(workcenter.resource_id.id, 0.0),
            }
            for workcenter in workcenters
        }

    def _web_gantt_progress_bar_employee_assigned_ids(self, res_ids, start, stop):
        self.env['mrp.workorder'].check_access('read')
        employees = self.env['hr.employee'].search([('id', 'in', res_ids)])
        workorders = self.env['mrp.workorder'].search([
            ('employee_assigned_ids', 'in', res_ids),
            ('state', 'not in', ['done', 'cancel']),
            ('date_start', '<=', stop.replace(tzinfo=None)),
            ('date_finished', '>=', start.replace(tzinfo=None)),
        ])
        planned_hours = defaultdict(float)
        employees_work_intervals, _dummy = employees.resource_id._get_valid_work_intervals(start, stop)
        for workorder in workorders:
            max_start = max(start, workorder.date_start.replace(tzinfo=UTC))
            min_finished = min(stop, workorder.date_finished.replace(tzinfo=UTC))
            for employee in workorder.employee_assigned_ids:
                interval = Intervals([(max_start, min_finished, self.env['resource.calendar.attendance'])])
                work_intervals = interval & employees_work_intervals[employee.resource_id.id]
                planned_hours[employee] += sum_intervals(work_intervals)
        work_hours = {
            id: sum_intervals(work_intervals) for id, work_intervals in employees_work_intervals.items()
        }
        return {
            employee.id: {
                'value': planned_hours[employee],
                'max_value': work_hours.get(employee.resource_id.id, 0.0),
            }
            for employee in employees
        }

    def _get_employee_domain(self):
        """
        Returns a domain for employees, who satisfy the following:
         - Employee currently assigned to any work order (not done, not cancelled)
         - Employee assigned to any work order in the last 30 days
        """
        date_limit = fields.Datetime.now() - timedelta(days=30)

        workorders = self.search_read(
            ['&',
                ('employee_assigned_ids', '!=', False),
                '|',
                    ('state', 'not in', ['done', 'cancel']),
                    ('date_start', '>=', date_limit),
            ],
            ['employee_assigned_ids'],
        )

        employee_ids = set()
        for wo in workorders:
            employee_ids.update(wo['employee_assigned_ids'])

        return [('id', 'in', list(employee_ids))]

    @api.model
    def get_gantt_data(self, domain, groupby, read_specification, limit=None, offset=0, unavailability_fields=None, progress_bar_fields=None, start_date=None, stop_date=None, scale=None):
        gantt_data = super(MrpWorkorder, self.with_context(display_complete_name=True)).get_gantt_data(domain, groupby, read_specification, limit=limit, offset=offset, unavailability_fields=unavailability_fields, progress_bar_fields=progress_bar_fields, start_date=start_date, stop_date=stop_date, scale=scale)
        if groupby == ['employee_assigned_ids']:
            employee_domain = []
            for leaf in domain:
                if isinstance(leaf, list) and leaf[0] == 'employee_assigned_ids':
                    employee_domain.append([('name', leaf[1], leaf[2])])
            search_domain = Domain.AND([self._get_employee_domain(), employee_domain and Domain.OR(employee_domain)])
            employees = self.env['hr.employee'].search_read(search_domain, ['id', 'name'])
            employees_ids = set()
            workcenter_ids = set()
            group_records = {
                group['employee_assigned_ids']: group['__record_ids'] for group in gantt_data['groups']
            }
            groups = []
            if False in group_records:
                groups.append({
                    'employee_assigned_ids': False,
                    '__record_ids': group_records.get(False)
                })
            for employee in employees:
                employees_ids.add(employee['id'])
                groups.append({
                    'employee_assigned_ids': (employee['id'], employee['name']),
                    '__record_ids': group_records.get((employee['id'], employee['name']), [])
                })
            for workorder in gantt_data.get('records', []):
                if workcenter := workorder.get('workcenter_id'):
                    workcenter_ids.add(workcenter['id'])
            gantt_data['groups'] = groups
            gantt_data['length'] = len(groups)
            # re-fill unavailabilities since we added groups
            start, stop = fields.Datetime.from_string(start_date), fields.Datetime.from_string(stop_date)
            gantt_data['unavailabilities']['employee_assigned_ids'] = self._gantt_unavailability('employee_assigned_ids', employees_ids, start, stop, scale)
            gantt_data['unavailabilities']['workcenter_id'] = self._gantt_unavailability('workcenter_id', workcenter_ids, start, stop, scale)
        return gantt_data

    @api.model
    def _gantt_progress_bar(self, field, res_ids, start, stop):
        start, stop = start.replace(tzinfo=UTC), stop.replace(tzinfo=UTC)
        today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        start = max(start, today)
        if field == 'workcenter_id':
            return self._web_gantt_progress_bar_workcenter_id(res_ids, start, stop)
        if field == 'employee_assigned_ids':
            return self._web_gantt_progress_bar_employee_assigned_ids(res_ids, start, stop)
        raise NotImplementedError("This Progress Bar is not implemented.")

    @api.model
    def _gantt_unavailability(self, field, res_ids, start, stop, scale):
        """Get unavailabilities data to display in the Gantt view."""
        if field == 'workcenter_id':
            workcenters = self.env['mrp.workcenter'].browse(res_ids)
            unavailable_intervals = workcenters.resource_id._get_unavailable_intervals(start, stop)
            result = {}
            for workcenter in workcenters:
                result[workcenter.id] = [
                    {'start': interval[0], 'stop': interval[1]}
                    for interval in unavailable_intervals.get(workcenter.resource_id.id, [])
                ]
            return result
        if field == 'employee_assigned_ids':
            employees = self.env['hr.employee'].browse(res_ids)
            unavailable_intervals = employees.resource_id._get_unavailable_intervals(start, stop)
            result = {}
            for employee in employees:
                result[employee.id] = [
                    {'start': interval[0], 'stop': interval[1]}
                    for interval in unavailable_intervals.get(employee.resource_id.id, [])
                ]
            return result
        return super()._gantt_unavailability(field, res_ids, start, stop, scale)

    @api.model
    def get_shopfloor_limit(self):
        return self.env['ir.config_parameter'].sudo().get_int("mrp_workorder.wo_shop_floor_maximum_card_count") or 40

    def _should_be_pending(self):
        return self.is_user_working and self.working_state != 'blocked' and len(self.employee_ids.ids) == 0

    def _should_start(self):
        if self.working_state != 'blocked' and self.state in ('ready', 'blocked', 'progress'):
            if self.env['hr.employee'].get_session_owner():
                return True
            else:
                self.button_start(bypass=True)
        return False

    @api.depends('employee_ids')
    def _compute_employee_id(self):
        main_employee_connected = self.env['hr.employee'].get_session_owner()
        self.employee_id = main_employee_connected
        self.employee_name = self.env['hr.employee'].browse(main_employee_connected).name

    @api.depends('all_employees_allowed')
    def _all_employees_allowed(self):
        for wo in self:
            wo.all_employees_allowed = len(wo.allowed_employees) == 0

    def start_employee(self, employee_id):
        self.ensure_one()
        if employee_id in self.employee_ids.ids and any(not t.date_end for t in self.time_ids if t.employee_id.id == employee_id):
            return
        self.employee_ids = [Command.link(employee_id)]
        time_data = self._prepare_timeline_vals(self.duration, fields.Datetime.now())
        time_data['employee_id'] = employee_id
        self.env['mrp.workcenter.productivity'].create(time_data)
        self.state = "progress"

    def stop_employee(self, employee_ids):
        self.employee_ids = [Command.unlink(emp) for emp in employee_ids]
        self.env['mrp.workcenter.productivity'].search([
            ('employee_id', 'in', employee_ids),
            ('workorder_id', 'in', self.ids),
            ('date_end', '=', False)
        ])._close()

    def get_employee_duration(self, employee_id):
        self.ensure_one()
        now = self.env.cr.now()
        closed_duration = sum(self.time_ids.filtered(lambda t: t.employee_id.id == employee_id).mapped('duration'))
        opened_duration = sum(self.time_ids.filtered(lambda t: t.employee_id.id == employee_id and not t.date_end).mapped(lambda t: t and max((now - t.date_start).total_seconds() / 60, 0)), False)
        return closed_duration, opened_duration

    def set_employee_duration(self, employee_id, duration):
        return self._set_duration(employee_id, duration)

    def _should_start_timer(self):
        """ Return True if the timer should start once the workorder is opened."""
        self.ensure_one()
        return False

    def _cal_cost(self, date=False):
        total_workcenter_cost = super()._cal_cost(date)
        for wo in self:
            if wo._should_estimate_cost():
                total_workcenter_cost += (wo.duration_expected / 60) * (wo.employee_costs_hour or wo.workcenter_id.employee_costs_hour)
            elif date:
                total_workcenter_cost += sum(wo.time_ids.filtered(lambda t: t.date_end and t.date_end <= date).mapped('total_cost'))
            else:
                total_workcenter_cost += sum(wo.time_ids.mapped('total_cost'))
        return total_workcenter_cost

    def button_pending(self):
        Employee = self.env['hr.employee']
        # Determine current employee
        if not self.env.context.get('mrp_display'):
            employee = self.env.user.employee_id
        else:
            connected_employees = Employee.get_employees_connected()
            if not connected_employees:
                raise UserError(_("You need to log in to process this work order."))
            employee = Employee.get_session_owner()
        if employee:
            # Stop productivity only for the current employee
            self.stop_employee([employee.id])
        super().button_pending()

    def action_mark_as_done(self):
        if self.env.context.get('mrp_display'):
            main_employee_connected = self.env['hr.employee'].get_session_owner()
            if not main_employee_connected:
                raise UserError(_('You must be logged in to process some of these work orders.'))
        else:
            main_employee_connected = self.env.user.employee_id.id
            if not main_employee_connected:
                if self.env.user.has_group('hr.group_hr_user'):
                    raise RedirectWarning(
                        message=_("You need to link this user to an employee of this company to process these work orders."),
                        action={
                            'name': _("Create Employee"),
                            'type': 'ir.actions.act_window',
                            'res_model': 'hr.employee',
                            'views': [[False, 'form']],
                            'target': 'new',
                            'context': {'default_user_id': self.env.user.id},
                        },
                        button_text=_("Create Employee"),
                    )
                else:
                    raise UserError(_("You need to link this user to an employee of this company to process these work orders."))
        for wo in self:
            if len(wo.allowed_employees) != 0 and main_employee_connected not in [wo.id for wo in wo.allowed_employees]:
                raise UserError(_('You are not allow to work on some of these work orders.'))
        res = self.button_finish()
        if isinstance(res, dict) and res.get('res_model') == 'mrp.production.backorder':
            return res

        loss_id = self.env['mrp.workcenter.productivity.loss'].search([('loss_type', '=', 'productive')], limit=1)
        if len(loss_id) < 1:
            raise UserError(_("You need to define at least one productivity loss in the category 'Productive'. Create one from the Manufacturing app, menu: Configuration / Productivity Losses."))

        self.state = 'done'
        self._set_default_time_log(loss_id)

    def _set_default_time_log(self, loss_id):
        productivity = []
        for wo in self:
            if not wo.time_ids:
                now = fields.Datetime.now()
                date_start = datetime.fromtimestamp(now.timestamp() - ((wo.duration_expected * 60) // 1))
                date_end = now
                connected_employee = wo._get_connected_employee()
                productivity.append({
                    'workorder_id': wo.id,
                    'workcenter_id': wo.workcenter_id.id,
                    'description': _('Time Tracking: %(user)s', user=connected_employee.name),
                    'date_start': date_start,
                    'date_end': date_end,
                    'loss_id': loss_id[0].id,
                    'user_id': self.env.user.id,
                    'company_id': wo.company_id.id,
                    'employee_id': connected_employee.id,
                })
        self.env['mrp.workcenter.productivity'].create(productivity)

    def _compute_expected_operation_cost(self, without_employee_cost=False):
        expected_machine_cost = super()._compute_expected_operation_cost()
        if without_employee_cost:
            return expected_machine_cost
        expected_labour_cost = (self.duration_expected / 60) * self.workcenter_id.employee_costs_hour * (self.operation_id.employee_ratio or 1)
        return expected_machine_cost + expected_labour_cost

    def _compute_current_operation_cost(self):
        current_machine_cost = super()._compute_current_operation_cost()
        current_labour_cost = sum(self.time_ids.mapped('total_cost'))
        return current_machine_cost + current_labour_cost

    def end_all(self):
        self.employee_ids = [Command.clear()]
        return super().end_all()

    def action_mrp_workorder_dependencies(self, planning_by):
        action = self.env['ir.actions.act_window']._for_xml_id('mrp.action_mrp_workorder_production')
        refs = {
            'workcenter': 'mrp_workorder.mrp_workorder_view_gantt',
            'employee': 'mrp_workorder.mrp_workorder_view_gantt_employee',
        }
        ref = refs[planning_by]
        action['views'] = [
            (self.env.ref(ref).id, 'gantt'),
            (self.env.ref('mrp.workcenter_line_kanban').id, 'kanban'),
        ] + [(id, kind) for id, kind in action['views'] if kind not in ['kanban', 'gantt']]
        action['domain'] = [('state', '!=', 'cancel')]
        action['context'] = {}
        if planning_by == 'workcenter':
            action['context'] = {
                'show_workcenter_status': True,
                'search_default_filter_planned': True,
                'search_default_draft': True,
                'search_default_ready': True,
                'search_default_blocked': True,
                'search_default_progress': True,
            }
        return action

    def action_mrp_workorder_planning(self):
        action = self.env["ir.actions.act_window"]._for_xml_id("mrp.action_mrp_workorder_production")
        gantt_view = 'mrp_workorder.mrp_workorder_view_gantt'
        action['views'] = [
            (self.env.ref('mrp.workcenter_line_kanban').id, 'kanban'),
            (self.env.ref(gantt_view).id, 'gantt'),
        ] + [(id, kind) for id, kind in action['views'] if kind not in ['kanban', 'gantt']]
        action["context"] = {
            'search_default_draft': True,
            "search_default_ready": True,
            "search_default_blocked": True,
            "search_default_filter_planned": True,
            "search_default_progress": True,
            "show_workcenter_status": True,
        }
        return action

    def _prepare_timeline_vals(self, duration, date_start, date_end=False, employee_id=None):
        time_data = super()._prepare_timeline_vals(duration=duration, date_start=date_start, date_end=date_end)
        employee = self.env['hr.employee'].browse(employee_id) if employee_id is not None else self._get_connected_employee()
        time_data['employee_id'] = employee.id
        time_data['description'] = _('Time Tracking: %(user)s', user=employee.name)
        return time_data

    def set_qty_producing(self):
        self.ensure_one()
        if not self.production_bom_id.continuous:
            self.production_id.qty_producing = self.qty_produced
            self.production_id.set_qty_producing()

        # Find first uncompleted step of type register production (if it exists) in the chain
        current_check = self.check_ids.filtered(lambda c: not c.previous_check_id)[:1]
        while current_check and current_check.next_check_id and (current_check.test_type != 'register_production' or current_check.quality_state != 'none'):
            current_check = current_check.next_check_id

        if current_check and current_check.test_type == 'register_production' and current_check.quality_state == 'none':
            # Check exists already, mark as done.
            current_check.action_next()
        elif not any(c.test_type == 'register_production' for c in self.check_ids):
            # Add a register production step for this WO only (at the front of the list)
            first_check = self.check_ids.filtered(lambda c: not c.previous_check_id)
            new_check = self.env['quality.check'].create([{
                'title': _('Register Production'),
                'test_type_id': self.env.ref('mrp_workorder.test_type_register_production').id,
                'workorder_id': self.id,
                'quality_state': 'pass',
                'production_id': self.production_id.id,
                'product_id': self.product_id.id,
                'lot_ids': self.production_id.lot_producing_ids.ids,
                'team_id': self.env['quality.alert.team']._get_quality_team(
                    self.env['quality.alert.team']._check_company_domain(
                        self.company_id.id or self.env.context.get('default_company_id', self.env.company.id)
                    ))
            }])
            if first_check:
                new_check._insert_in_chain('before', first_check)
            else:
                self.current_quality_check_id = new_check

    def _get_connected_employee(self):
        if self.env.context.get('mrp_display'):
            if (self.env.context.get('employee_id')):
                connected_employee_id = self.env.context.get('employee_id')
            else:
                connected_employee_id = self.env['hr.employee'].get_session_owner()
            connected_employee = self.env['hr.employee'].browse(connected_employee_id)
        else:
            if self.employee_assigned_ids:
                connected_employee = self.employee_assigned_ids[0]
            else:
                connected_employee = self.env.user.employee_id

        return connected_employee
