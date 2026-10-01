# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, Command, _
from odoo.exceptions import UserError


class MaintenanceStage(models.Model):
    _inherit = 'maintenance.stage'

    create_leaves = fields.Boolean('Request Confirmed', default=True,
        help="When this box is unticked, and the maintenance is of the type 'Work Center', no leave is created on the respective work center when a maintenance request is created.\n"
            "If the box is ticked, the work center is automatically blocked for the listed duration, either at the specified date, or as soon as possible, if the work center is unavailable then.")

    def write(self, vals):
        res = super().write(vals)
        if 'create_leaves' in vals:
            maintenance_requests = self.env['maintenance.request'].search([('maintenance_for', '=', 'workcenter'), ('stage_id', 'in', self.ids)])
            maintenance_requests._recreate_leaves()
        return res


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"
    _check_company_auto = True

    workcenter_id = fields.Many2one(
        'mrp.workcenter', string='Work Center', check_company=True, index='btree_not_null')

    def button_mrp_workcenter(self):
        self.ensure_one()
        return {
            'name': _('work centers'),
            'view_mode': 'form',
            'res_model': 'mrp.workcenter',
            'view_id': self.env.ref('mrp.mrp_workcenter_view').id,
            'type': 'ir.actions.act_window',
            'res_id': self.workcenter_id.id,
            'context': {
                'default_company_id': self.company_id.id
            }
        }


class MaintenanceRequest(models.Model):
    _inherit = "maintenance.request"
    _check_company_auto = True

    production_id = fields.Many2one(
        'mrp.production', string='Manufacturing Order', check_company=True, index='btree_not_null')
    workorder_id = fields.Many2one(
        'mrp.workorder', string='Work Order', check_company=True)
    production_company_id = fields.Many2one(string='Production Company', related='production_id.company_id')
    company_id = fields.Many2one(domain="[('id', '=?', production_company_id)]")
    maintenance_for = fields.Selection([
        ('equipment', 'Equipment'),
        ('workcenter', 'Work Center')],
        string='For', default='equipment', required=True)
    equipment_id = fields.Many2one(compute='_compute_equipment_id', store=True, readonly=False)
    workcenter_id = fields.Many2one('mrp.workcenter', string='Work Center', compute='_compute_workcenter_id',
                                store=True, readonly=False, check_company=True, index='btree_not_null',
                                group_expand='_read_group_workcenter_id')
    block_workcenter = fields.Boolean('Block Workcenter', help="It won't be possible to plan work orders or other maintenances on this workcenter during this time.")
    recurring_leaves_count = fields.Integer('Additional Leaves to Plan Ahead', help='Block the workcenter for this many time slots in the future in advance.')
    leave_ids = fields.Many2many('resource.calendar.leaves', string="Leaves")

    @api.depends('maintenance_for')
    def _compute_equipment_id(self):
        self.filtered(lambda mr: mr.maintenance_for == 'workcenter' and mr.equipment_id).equipment_id = False

    @api.depends('maintenance_for', 'equipment_id')
    def _compute_workcenter_id(self):
        for request in self:
            if request.maintenance_for == 'equipment':
                request.workcenter_id = request.equipment_id.workcenter_id

    @api.depends('workcenter_id')
    def _compute_maintenance_team_id(self):
        for request in self:
            if request.workcenter_id and request.workcenter_id.maintenance_team_id:
                request.maintenance_team_id = request.workcenter_id.maintenance_team_id
        return super()._compute_maintenance_team_id()

    @api.depends('workcenter_id')
    def _compute_user_ids(self):
        for request in self:
            if request.maintenance_for == 'workcenter':
                request.user_ids = request.workcenter_id.technician_user_id
        return super()._compute_user_ids()

    @api.model_create_multi
    def create(self, vals_list):
        allowed_to_raise = not self  # self is empty during create; it contains records during copy.
        res = super().create(vals_list)
        res._recreate_leaves(raise_on_schedule_date_already_planned=allowed_to_raise)  # do not raise when copying recurrent request
        return res

    def write(self, vals):
        previous_create_leaves = {request.id: request.stage_id.create_leaves for request in self}
        res = super().write(vals)
        if 'leave_ids' not in vals and any(k in vals for k in ['workcenter_id', 'schedule_date', 'schedule_end',
                                                               'maintenance_type',
                                                               'recurring_maintenance',
                                                               'repeat_interval', 'repeat_unit', 'repeat_type', 'repeat_until',
                                                               'block_workcenter',
                                                               'recurring_leaves_count']):
            self._recreate_leaves()
        elif 'stage_id' in vals:
            self.filtered(lambda mr: mr.stage_id.create_leaves != previous_create_leaves[mr.id])._recreate_leaves()
        return res

    def unlink(self):
        self.leave_ids.unlink()
        return super().unlink()

    def _read_group_workcenter_id(self, records, domain):
        """ Read group customization in order to display all the workcenter in
            the gantt/kanban view, even if they have no maintenance assigned.
        """
        return self.env['mrp.workcenter'].search([])

    def _recreate_leaves(self, raise_on_schedule_date_already_planned=True):
        """Allocate a new leave (and the early preventive ones) for the maintenance
        based on schedule date and duration.
        """
        self.leave_ids.unlink()
        for request in self:
            if request.state == 'cancelled':
                continue
            if request.maintenance_for != 'workcenter':
                continue
            if not request.schedule_date:
                continue
            if not request.workcenter_id:
                raise UserError(_("The workcenter is missing for %s.", request.display_name))
            if not request.block_workcenter:
                continue
            if request.state == 'done' or not request.stage_id.create_leaves:
                continue
            desired_date = request.schedule_date
            duration = request.duration or 1

            # Use '_get_first_flexible_available_slot' to find the first flexible available slot as maintenance can be
            # scheduled at a non working hours unlike work orders.
            if desired_date != request.workcenter_id._get_first_flexible_available_slot(desired_date, duration)[0] \
                and raise_on_schedule_date_already_planned:
                raise UserError(self.env._("Manufacturing Orders are already scheduled for this time slot."))

            count = 1
            if request.maintenance_type == 'preventive' and request.recurring_maintenance:
                count += request.recurring_leaves_count
            date = desired_date
            leave_ids_vals = []
            text = ""
            for _i in range(count):
                from_date, to_date = request.workcenter_id._get_first_flexible_available_slot(date, duration)
                if not from_date or not to_date:
                    text = self.env._("No available slot within 700 days after the planned start.")
                    break
                leave_ids_vals.append(Command.create({
                    'name': request.display_name,
                    'resource_id': request.workcenter_id.resource_id.id,
                    'calendar_id': request.workcenter_id.resource_calendar_id.id,
                    'date_from': from_date,
                    'date_to': to_date,
                    'count_as': 'absence',
                }))
                date += relativedelta(**{f"{request.repeat_unit}s": request.repeat_interval})
                if request.repeat_type == 'until' and date.date() > request.repeat_until:
                    break
            effective_date = leave_ids_vals and leave_ids_vals[0][2]['date_from']
            date_to = leave_ids_vals and leave_ids_vals[0][2]['date_to']
            request.write({
                'schedule_date': effective_date,
                'schedule_end': date_to,
                'leave_ids': leave_ids_vals,
            })
            if effective_date != desired_date:
                text = text or self.env._("The schedule has changed from %(desired_date)s to %(effective_date)s due to planned manufacturing orders.", desired_date=desired_date.astimezone(self.env.tz), effective_date=effective_date.astimezone(self.env.tz))
                self.activity_schedule(
                    'mail.mail_activity_data_warning',
                    note=text,
                    user_id=self.env.uid,
                )

    def cancel_equipment_request(self):
        super().cancel_equipment_request()
        self.leave_ids.unlink()
        self.write({'block_workcenter': False, 'recurring_leaves_count': 0})

    @api.model
    def _gantt_unavailability(self, field, res_ids, start, stop, scale):
        if field != 'workcenter_id':
            return super()._gantt_unavailability(field, res_ids, start, stop, scale)
        return self.env['mrp.workcenter']._get_gantt_unavailability(res_ids, start, stop, from_model=self._name)
