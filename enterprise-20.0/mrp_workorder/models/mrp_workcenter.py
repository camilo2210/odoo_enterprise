# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from ast import literal_eval
from odoo import models, fields, api
from odoo.tools import float_is_zero
from odoo.http import request


class MrpWorkcenter(models.Model):
    _name = 'mrp.workcenter'
    _inherit = ['hr.mixin', 'mrp.workcenter']

    employee_ids = fields.Many2many(
        'hr.employee', string="employees with access",
        help='if left empty, all employees can log in to the workcenter', store=True,
        readonly=False)
    currency_id = fields.Many2one(related='company_id.currency_id')
    employee_costs_hour = fields.Monetary(string='Employee Hourly Cost', currency_field='currency_id', default=0.0)

    def action_work_order(self):
        if self.env.user.has_group('mrp_workorder.group_mrp_wo_shop_floor') and not self.env.context.get('desktop_list_view', False):
            action = self.env["ir.actions.actions"]._for_xml_id("mrp_workorder.action_mrp_display")
        else:
            action = super().action_work_order()
        context = action.get('context', '{}')
        if 'active_id' not in context:
            context = context[:-1] + ",'workcenter_id': active_id}"
        context = context.replace('active_id', str(self.id))
        action['context'] = dict(literal_eval(context), employee_id=request.session.get('employee_id'), shouldHideNewWorkcenterButton=True)
        if self.env.context.get("view_mode"):
            del action["mobile_view_mode"]
            del action["views"]
            action["view_mode"] = self.env.context["view_mode"]
        return action

    @api.model
    def get_employee_barcode(self, barcode):
        return self.env['hr.employee'].sudo().search([("barcode", "=", barcode)], limit=1).id

    @api.depends('time_ids', 'time_ids.date_end', 'time_ids.loss_type')
    def _compute_working_state(self):
        self.working_state = 'normal'
        time_log = self.env['mrp.workcenter.productivity'].search([
            ('workcenter_id', 'in', self.ids),
            ('date_end', '=', False),
        ])
        for time in time_log:
            if time.loss_type in ('productive', 'performance'):
                # the productivity line has a `loss_type` that means the workcenter is being used
                time.workcenter_id.working_state = 'done'
            else:
                # the workcenter is blocked
                time.workcenter_id.working_state = 'blocked'

    def action_enable_routings(self):
        self.env['res.config.settings'].create([{'group_mrp_routings': True}]).execute()

    def action_open_workorders(self, from_gantt_view=False, date_to_plan_on=False):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("Plan Work Orders in %(workcenter)s", workcenter=self.name),
            'res_model': 'mrp.workorder',
            'domain': [('state', 'not in', ['draft', 'done', 'cancel'])],
            'views': [(self.env.ref('mrp_workorder.mrp_workcenter_workorders_tree_view').id if from_gantt_view else False, 'list')],
            'search_view_id': (self.env.ref('mrp.view_mrp_production_workorder_form_view_filter').id, 'search'),
            'context': {
                'search_default_workcenter_id': self.id,
                'search_default_ready': True,
                'search_default_blocked': True,
                'search_default_filter_to_plan': True,
                'date_to_plan_on': date_to_plan_on,
                'workcenter_to_plan_on': self.id,
            },
        }


class MrpWorkcenterProductivity(models.Model):
    _inherit = "mrp.workcenter.productivity"

    employee_id = fields.Many2one(
        'hr.employee', string="Employee", compute='_compute_employee',
        help='employee that record this working time', store=True, readonly=False)
    employee_cost = fields.Monetary('employee_cost', compute='_compute_employee_cost', default=0, store=True)
    total_cost = fields.Float('Cost', compute='_compute_total_cost')
    currency_id = fields.Many2one(related='company_id.currency_id')

    @api.depends('employee_id.hourly_cost')
    def _compute_employee_cost(self):
        for time in self:
            if time.workorder_id.state == 'done' and not float_is_zero(time.employee_cost, 2):
                continue

            if time.employee_id and not float_is_zero(time.employee_id.hourly_cost, 2):
                time.employee_cost = time.employee_id.hourly_cost
            else:
                time.employee_cost = time.workcenter_id.employee_costs_hour

    @api.depends('duration', 'employee_cost')
    def _compute_total_cost(self):
        for time in self:
            time.total_cost = time.employee_cost * time.duration / 60

    @api.depends('user_id')
    def _compute_employee(self):
        for time in self:
            if time.user_id and time.user_id.employee_id:
                time.employee_id = time.user_id.employee_id

    def _check_open_time_ids(self):
        # TODO make check on employees
        pass
