# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
import logging

from odoo import api, fields, models

from odoo.exceptions import AccessError, UserError
from odoo.tools import convert
from odoo.tools.misc import clean_context, format_date

_logger = logging.getLogger(__name__)


class HrAppraisal(models.Model):
    _name = 'hr.appraisal'
    _inherit = ['hr.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = "Employee Appraisal"
    _order = 'state, date_close, id desc'
    _rec_name = 'employee_id'
    _mail_post_access = 'read'

    def _get_default_employee(self):
        if self.env.context.get('active_model') in ('hr.employee', 'hr.employee.public') and 'active_id' in self.env.context:
            return self.env.context.get('active_id')
        elif self.env.context.get('active_model') == 'res.users' and 'active_id' in self.env.context:
            return self.env['res.users'].browse(self.env.context['active_id']).employee_id
        if not self.env.user.has_group('hr_appraisal.group_hr_appraisal_user'):
            return self.env.user.employee_id

    active = fields.Boolean(default=True)
    employee_id = fields.Many2one(
        'hr.employee', required=True, string='Employee', index=True,
        default=_get_default_employee, ondelete='cascade')
    employee_user_id = fields.Many2one('res.users', string="Employee User", related='employee_id.user_id')
    company_id = fields.Many2one('res.company', related='employee_id.company_id', store=True)
    department_id = fields.Many2one(
        'hr.department', compute='_compute_department_id', string='Department', store=True)
    job_id = fields.Many2one('hr.job', compute='_compute_job_id', string='Job', store=True)
    image_128 = fields.Image(related='employee_id.image_128')
    image_1920 = fields.Image(related='employee_id.image_1920')
    avatar_128 = fields.Image(related='employee_id.avatar_128')
    avatar_1920 = fields.Image(related='employee_id.avatar_1920')
    last_appraisal_id = fields.Many2one('hr.appraisal', related='employee_id.last_appraisal_id')
    employee_appraisal_count = fields.Integer(related='employee_id.appraisal_count')
    uncomplete_goals_count = fields.Integer(related='employee_id.uncomplete_goals_count')
    appraisal_template_id = fields.Many2one('hr.appraisal.template', string="Appraisal Template", compute="_compute_appraisal_template",
        check_company=True, store=True, readonly=False, domain="[('department_ids', 'in', [department_id, False])]")
    employee_feedback_template = fields.Html(compute='_compute_feedback_templates', translate=True)
    manager_feedback_template = fields.Html(compute='_compute_feedback_templates', translate=True)

    date_close = fields.Date(
        string='Appraisal Date', help='Closing date of the current appraisal', required=True, index=True,
        default=lambda self: fields.Date.context_today(self) + relativedelta(months=+1))
    next_appraisal_date = fields.Date(
        string='Next Appraisal Date', help='Date where the new appraisal will be automatically created',
        compute='_compute_next_appraisal_date', inverse='_inverse_next_appraisal_date', readonly=False)
    state = fields.Selection(
        [('1_new', 'Draft'),
         ('2_pending', 'Ongoing'),
         ('3_done', 'Done')],
        string='Status', tracking=True, required=True, copy=False,
        default='1_new', index=True, group_expand=True)
    manager_ids = fields.Many2many(
        'hr.employee', 'appraisal_manager_rel', 'hr_appraisal_id',
        default=lambda self: self.env.user.employee_id,
        bypass_search_access=True,
        context={'active_test': False},
        domain="[('id', '!=', employee_id), ('active', '=', True), '|', ('company_id', '=', False), ('company_id', 'in', allowed_company_ids)]")
    is_manager = fields.Boolean(compute='_compute_user_manager_rights')
    employee_autocomplete_ids = fields.Many2many(
        "hr.employee",
        compute="_compute_employee_autocomplete",
        compute_sudo=True,
        bypass_search_access=True,
    )
    waiting_feedback = fields.Boolean(
        string="Waiting Feedback from Employee/Managers", compute='_compute_waiting_feedback')
    employee_feedback = fields.Html(compute='_compute_employee_feedback', store=True, readonly=False, groups="hr_appraisal.group_hr_appraisal_user")
    accessible_employee_feedback = fields.Html(compute='_compute_accessible_employee_feedback', inverse="_inverse_accessible_employee_feedback")
    show_employee_feedback_full = fields.Boolean(compute='_compute_show_employee_feedback_full')
    manager_feedback = fields.Html(compute='_compute_manager_feedback', store=True, readonly=False, groups="hr_appraisal.group_hr_appraisal_user")
    accessible_manager_feedback = fields.Html(compute='_compute_accessible_manager_feedback', inverse="_inverse_accessible_manager_feedback")
    show_manager_feedback_full = fields.Boolean(compute='_compute_show_manager_feedback_full')
    employee_feedback_published = fields.Boolean(string="Employee Feedback Published", default=False, tracking=True,
        help="If greened, the manager will be able to see and edit your feedback. Otherwise, your feedback is blurred and visible only to you.")
    manager_feedback_published = fields.Boolean(string="Manager Feedback Published", default=False, tracking=True,
        help="If greened, the employee will be able to see your feedback. Otherwise, your feedback is blurred and visible only to you.")
    can_see_employee_publish = fields.Boolean(compute='_compute_buttons_display')
    can_see_manager_publish = fields.Boolean(compute='_compute_buttons_display')
    assessment_note = fields.Many2one('hr.appraisal.note', string="Final Rating", help="This field is not visible to the Employee.", check_company=True)
    note = fields.Html(string="Private Note")
    appraisal_plan_posted = fields.Boolean()
    appraisal_properties = fields.Properties("Properties", definition="department_id.appraisal_properties_definition", precompute=False)
    duplicate_appraisal_id = fields.Many2one('hr.appraisal', compute='_compute_duplicate_appraisal_id', export_string_translation=False, store=False)

    def _read_manager_only_fields(self):
        """
        :return: A set of restricted field names.
        :rtype: set[str]
        """
        return {
            "assessment_note",
            "note",
        }

    def _write_manager_only_fields(self):
        """
        :return: A set of restricted field names.
        :rtype: set[str]
        """
        return {
            "assessment_note",
            "manager_feedback_published",
            "note",
            "state",
        }

    def _check_create_access(self, vals, manager_only_fieldset):
        """
        :param vals: A value dictionary for the newly created record.
        :type vals: dict
        :param manager_only_fieldset: A set of restricted field names.
        :type manager_only_fieldset: set[str]
        :raises AccessError: If a non-manager creates an appraisal with restricted fields set to non-whitelisted values.
        """
        if self.env.su:
            return
        if self.is_manager and self.employee_id not in self.env.user.employee_ids:
            return

        restricted_fields = manager_only_fieldset & set(vals.keys())
        restricted_fields_defaults = self.with_context(clean_context(self.env.context)).default_get(restricted_fields)
        for field in restricted_fields:
            if restricted_fields_defaults.get(field, False) != vals.get(field, False):
                raise AccessError(
                    self.env._(
                        "Unfortunately you don't have access to modify the value of the following field: %(inaccessible_field)s",
                        inaccessible_field=self._fields[field].get_description(self.env)["string"],
                    ),
                )

    def _check_write_access(self, vals):
        """
        :param vals: The values dictionary passed to the write method.
        :type vals: dict
        :raises AccessError: If a non-manager writes non-whitelisted values to restricted fields.
        """
        if self.env.su:
            return

        # Limit changes to an appraisal after marking it done
        if any(a.state == "3_done" for a in self) and vals.get('state') != '2_pending':
            raise AccessError(self.env._("You cannot modify a finished appraisal."))

        # Limit changes to an appraisal depending on who is making the change
        manager_only_fields = vals.keys() & self._write_manager_only_fields()
        has_manager_write_access = all(
            bool(appraisal.is_manager and appraisal.employee_id not in self.env.user.employee_ids) for appraisal in self
        )
        if manager_only_fields and not has_manager_write_access:
            raise AccessError(
                self.env._(
                    "Unfortunately you don't have access to modify the value of the following fields: %(inaccessible_fields)s",
                    inaccessible_fields=", ".join(
                        self._fields[field].get_description(self.env)["string"] for field in manager_only_fields
                    ),
                ),
            )

    @api.depends('employee_id')
    def _compute_next_appraisal_date(self):
        for appraisal in self:
            emp = appraisal.employee_id.sudo()
            if emp.next_appraisal_date:
                appraisal.next_appraisal_date = max(emp.next_appraisal_date, fields.Date.today())

    def _inverse_next_appraisal_date(self):
        for appraisal in self:
            emp = appraisal.employee_id.sudo()
            if appraisal.next_appraisal_date:
                emp.next_appraisal_date = max(appraisal.next_appraisal_date, fields.Date.today())

    @api.depends('employee_id', 'manager_ids')
    def _compute_duplicate_appraisal_id(self):
        """
        Note: We only care for duplicate_appraisal_id when we create a
        new appraisal. This field is currently only used in form view
        and for performance reasons it should rather stay that way.
        """
        ongoing_appraisals = self.search([
            ('state', 'in', ['1_new', '2_pending']),
            ('employee_id', 'in', self.employee_id.ids),
            ('manager_ids', 'in', self.manager_ids.ids),
        ], order='date_close')
        self.duplicate_appraisal_id = False
        for appraisal in self:
            if appraisal.id or appraisal.state != '1_new':
                continue
            for ongoing_appraisal in ongoing_appraisals:
                if ongoing_appraisals.manager_ids == appraisal.manager_ids._origin\
                    and ongoing_appraisal.employee_id == appraisal.employee_id\
                        and ongoing_appraisal.id != appraisal.id:
                    appraisal.duplicate_appraisal_id = ongoing_appraisal.id
                    break

    @api.depends('employee_id.department_id', 'state')
    def _compute_department_id(self):
        for appraisal in self.filtered(lambda a: a.state == '1_new'):
            appraisal.department_id = appraisal.employee_id.department_id

    @api.depends('employee_id.job_id', 'state')
    def _compute_job_id(self):
        for appraisal in self.filtered(lambda a: a.state == '1_new'):
            appraisal.job_id = appraisal.employee_id.job_id

    @api.depends_context('uid')
    @api.depends('employee_id', 'manager_ids')
    def _compute_buttons_display(self):
        new_appraisals = self.filtered(lambda a: a.state == '1_new')
        new_appraisals.update({
            'can_see_employee_publish': False,
            'can_see_manager_publish': False,
        })
        user_employees = self.env.user.employee_ids
        is_manager = self.env.user.has_group('hr_appraisal.group_hr_appraisal_user')
        for appraisal in self:
            user_employee_in_appraisal_manager = bool(set(user_employees.ids) & set(appraisal.manager_ids.ids))
            # Appraisal manager can edit feedback in draft state
            appraisal.can_see_employee_publish = appraisal.employee_id in user_employees
            appraisal.can_see_manager_publish = user_employee_in_appraisal_manager
        for appraisal in self - new_appraisals:
            if is_manager and not appraisal.can_see_employee_publish and not appraisal.can_see_manager_publish:
                appraisal.can_see_employee_publish, appraisal.can_see_manager_publish = True, True

    @api.depends_context('uid')
    @api.depends('manager_ids', 'employee_id', 'employee_id.parent_id')
    def _compute_employee_autocomplete(self):
        self.employee_autocomplete_ids = self.env.user.get_employee_autocomplete_ids()

    @api.depends_context('uid')
    @api.depends('manager_ids', 'employee_id', 'employee_id.parent_id')
    def _compute_user_manager_rights(self):
        for appraisal in self:
            employees = self.env['hr.employee'].search([('id', 'child_of', self.env.user.employee_id.ids)])
            appraisal.is_manager =\
                self.env.user.has_group('hr_appraisal.group_hr_appraisal_user')\
                or bool(appraisal.employee_id.id in employees.ids)

    @api.depends_context('uid')
    @api.depends('employee_id', 'employee_feedback_published')
    def _compute_show_employee_feedback_full(self):
        for appraisal in self:
            is_appraisee = appraisal.employee_id.user_id == self.env.user
            appraisal.show_employee_feedback_full = is_appraisee and not appraisal.employee_feedback_published

    @api.depends_context('uid')
    @api.depends('manager_ids', 'manager_feedback_published')
    def _compute_show_manager_feedback_full(self):
        for appraisal in self:
            is_appraiser = self.env.user in appraisal.manager_ids.user_id
            appraisal.show_manager_feedback_full = is_appraiser and not appraisal.manager_feedback_published

    @api.depends('department_id', 'appraisal_template_id')
    def _compute_employee_feedback(self):
        for appraisal in self.filtered(lambda a: a.state in ['1_new', '2_pending']):
            employee_template = appraisal._get_appraisal_template('employee')
            if appraisal.state == '1_new':
                appraisal.employee_feedback = employee_template
            else:
                appraisal.employee_feedback = appraisal.employee_feedback or employee_template

    @api.depends('department_id', 'appraisal_template_id')
    def _compute_manager_feedback(self):
        for appraisal in self.filtered(lambda a: a.state in ['1_new', '2_pending']):
            manager_template = appraisal._get_appraisal_template('manager')
            if appraisal.state == '1_new':
                appraisal.manager_feedback = manager_template
            else:
                appraisal.manager_feedback = appraisal.manager_feedback or manager_template

    @api.depends('department_id', 'company_id', 'appraisal_template_id')
    def _compute_feedback_templates(self):
        for appraisal in self:
            appraisal.employee_feedback_template = appraisal._get_appraisal_template('employee')
            appraisal.manager_feedback_template = appraisal._get_appraisal_template('manager')

    @api.depends('department_id', 'company_id')
    def _compute_appraisal_template(self):
        all_appraisal_template_ids = self.env['hr.appraisal.template'].search(
            [('company_id', 'in', self.company_id.ids + [False])])
        for appraisal in self:
            current_template = appraisal.appraisal_template_id
            # Also keep a compatible generic template once the appraisal exists,
            # as it may then be a deliberate choice rather than the initial default.
            is_selected_generic_template = (
                appraisal._origin.id
                and current_template
                and not current_template.department_ids
                and current_template.company_id.id in [appraisal.company_id.id, False]
            )
            if is_selected_generic_template:
                appraisal.appraisal_template_id = current_template
            elif appraisal.employee_id and not appraisal.appraisal_template_id:
                appraisal.appraisal_template_id = next(
                    (
                        template
                        for template in all_appraisal_template_ids
                        if template.company_id.id in [appraisal.company_id.id, False]
                        and (
                            not template.department_ids
                            or appraisal.department_id in template.department_ids
                        )
                    ),
                    self.env['hr.appraisal.template'],
                )

    @api.depends('employee_feedback_published', 'manager_feedback_published')
    def _compute_waiting_feedback(self):
        for appraisal in self:
            appraisal.waiting_feedback = not appraisal.employee_feedback_published or not appraisal.manager_feedback_published

    @api.depends('employee_id', 'date_close')
    @api.depends_context('include_date_in_name')
    def _compute_display_name(self):
        if not self.env.context.get('include_date_in_name'):
            return super()._compute_display_name()
        for appraisal in self:
            appraisal.display_name = self.env._(
                "Appraisal for %(employee)s on %(date)s",
                employee=appraisal.employee_id.name, date=appraisal.date_close)

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        self = self.sudo()  # fields are not on the employee public
        if self.employee_id:
            manager = self.employee_id.parent_id or self.env.user.employee_id
            self.manager_ids = manager if manager != self.employee_id else False
            # Allow indirect managers to request appraisals for employees
            if self.env.user.employee_id != self.employee_id and not self.env.user.has_group('hr_appraisal.group_hr_appraisal_user'):
                self.manager_ids |= self.env.user.employee_id
            self.department_id = self.employee_id.department_id

    def subscribe_employees(self):
        for appraisal in self:
            partners_ids = (appraisal.manager_ids.sudo().related_partner_id + appraisal.employee_id.sudo().related_partner_id).ids
            appraisal.message_subscribe(partner_ids=partners_ids)

    def send_appraisal(self):
        # TDE FIXME: probably some cleanup to do here
        for appraisal in self:
            confirmation_mail_template = appraisal.company_id.appraisal_confirm_mail_template
            mapped_data = {
                **{appraisal.employee_id: confirmation_mail_template},
                **{manager: confirmation_mail_template for manager in appraisal.manager_ids}
            }
            for employee, mail_template in mapped_data.items():
                if not employee.work_email or not self.env.user.email or not mail_template:
                    continue
                ctx = {
                    'employee_to_name': appraisal.employee_id.name,
                    'recipient_users': employee.user_id,
                    'url': '/mail/view?model=%s&res_id=%s' % ('hr.appraisal', appraisal.id),
                }
                mail_template = mail_template.with_context(**ctx)
                subject = mail_template._render_field('subject', appraisal.ids)[appraisal.id]
                body = mail_template._render_field('body_html', appraisal.ids)[appraisal.id]
                # post the message
                mail_values = {
                    'email_from': self.env.user.email_formatted,
                    'author_id': self.env.user.partner_id.id,
                    'model': None,
                    'res_id': None,
                    'subject': subject,
                    'body_html': body,
                    'auto_delete': True,
                    'email_to': employee.work_email
                }
                mail_values['body_html'] = self.env['mail.render.mixin']._render_encapsulate(
                    'mail.mail_notification_light', mail_values['body_html'],
                    context_record=appraisal,
                    add_context={
                        'record_name': self.env._("Appraisal Request"),
                    },
                )
                self.env['mail.mail'].sudo().create(mail_values)

                from_cron = 'from_cron' in self.env.context
                # When cron creates appraisal, it creates specific activities
                # In this case, no need to create activities, not to be repetitive
                if employee.user_id and not from_cron:
                    appraisal.activity_schedule(
                        'mail.mail_activity_data_todo', appraisal.date_close,
                        summary=self.env._('Appraisal Form to Fill'),
                        note=self.env._('Fill appraisal for %s', appraisal.employee_id._get_html_link()),
                        user_id=employee.user_id.id)

    @api.model_create_multi
    def create(self, vals_list):
        appraisals = super().create(vals_list)
        appraisals_to_send = self.env['hr.appraisal']
        manager_only_fieldset = self._write_manager_only_fields()
        for appraisal, vals in zip(appraisals, vals_list):
            appraisal._check_create_access(vals, manager_only_fieldset)
            if vals.get('state') and vals['state'] == '2_pending':
                appraisals_to_send |= appraisal
            if vals.get('state') and vals['state'] == '1_new':
                appraisal.employee_id.sudo().write({
                    'last_appraisal_id': appraisal.id,
                })
        appraisals_to_send.send_appraisal()
        # TDE FIXME: check if we can use suggested recipients instead (master)
        appraisals.subscribe_employees()
        return appraisals

    @api.depends('employee_feedback', 'can_see_employee_publish', 'employee_feedback_published')
    def _compute_accessible_employee_feedback(self):
        for appraisal in self:
            if appraisal.can_see_employee_publish or appraisal.employee_feedback_published:
                appraisal.accessible_employee_feedback = appraisal.sudo().employee_feedback
            else:
                appraisal.accessible_employee_feedback = self.env._("Unpublished")

    def _inverse_accessible_employee_feedback(self):
        for appraisal in self:
            if appraisal.can_see_employee_publish:
                appraisal.sudo().employee_feedback = appraisal.accessible_employee_feedback
            else:
                raise AccessError(self.env._('The employee feedback cannot be changed by managers.'))

    @api.depends('manager_feedback', 'can_see_manager_publish', 'manager_feedback_published')
    def _compute_accessible_manager_feedback(self):
        for appraisal in self:
            if appraisal.can_see_manager_publish or appraisal.manager_feedback_published:
                appraisal.accessible_manager_feedback = appraisal.sudo().manager_feedback
            else:
                appraisal.accessible_manager_feedback = self.env._("Unpublished")

    def _inverse_accessible_manager_feedback(self):
        for appraisal in self:
            if appraisal.can_see_manager_publish:
                appraisal.sudo().manager_feedback = appraisal.accessible_manager_feedback
            else:
                raise AccessError(self.env._('The manager feedback cannot be changed by an employee.'))

    def _get_appraisal_template(self, template):
        self.ensure_one()
        if not self.appraisal_template_id:
            return False
        if template == 'employee':
            return self.appraisal_template_id.appraisal_employee_feedback_template
        else:
            return self.appraisal_template_id.appraisal_manager_feedback_template

    def _find_previous_appraisals(self):
        result = {}
        all_appraisals = self.env['hr.appraisal'].search([
            ('employee_id', 'in', self.mapped('employee_id').ids),
        ], order='employee_id, id desc')
        for appraisal in self:
            previous_appraisals = all_appraisals.filtered(lambda x: x.employee_id == appraisal.employee_id and x.id != appraisal.id and x.create_date < appraisal.create_date)
            if previous_appraisals:
                result[appraisal.id] = previous_appraisals[0]
        return result

    def write(self, vals):
        self._check_write_access(vals)

        force_published = self.env['hr.appraisal']
        if vals.get('employee_feedback_published'):
            user_employees = self.env.user.employee_ids
            force_published = self.filtered(lambda a: (a.is_manager) and not (a.employee_feedback_published or a.employee_id in user_employees))
        if vals.get('state') in ['2_pending', '3_done']:
            self.activity_ids.action_feedback()
            not_done_appraisal = self.env['hr.appraisal']
            for appraisal in self:
                appraisal.employee_id.sudo().write({
                    'last_appraisal_id': appraisal.id,
                })
                if appraisal.state != '3_done':
                    not_done_appraisal |= appraisal
            if vals.get('state') == '2_pending':
                vals['employee_feedback_published'] = False
                vals['manager_feedback_published'] = False
                not_done_appraisal.send_appraisal()
            else:
                vals['employee_feedback_published'] = True
                vals['manager_feedback_published'] = True
                self._appraisal_plan_post()
                if self.env.user.partner_id.email_formatted:
                    body = self.env._("The appraisal's status has been set to Done by %s", self.env.user.name)
                    for appraisal in self:
                        appraisal.message_notify(
                            body=body,
                            subject=self.env._("Your Appraisal has been completed"),
                            partner_ids=appraisal.message_partner_ids.ids,
                        )
                        appraisal.message_post(body=body)
        result = super().write(vals)
        if force_published:
            for appraisal in force_published:
                role = self.env._('Manager') if self.env.user.employee_id in appraisal.manager_ids else self.env._('Appraisal Officer')
                appraisal.message_post(body=self.env._('%(user)s decided, as %(role)s, to publish the employee\'s feedback', user=self.env.user.name, role=role))
        return result

    def unlink(self):
        previous_appraisals = self._find_previous_appraisals()
        for appraisal in self:
            # If current appraisal is the last_appraisal_id for the employee we should update last_appraisal_id bfore deleting
            if appraisal.employee_id and appraisal.employee_id.last_appraisal_id == appraisal:
                previous_appraisal = previous_appraisals.get(appraisal.id)
                appraisal.employee_id.sudo().write({
                    'last_appraisal_id': previous_appraisal.id if previous_appraisal else False,
                })
        return super(HrAppraisal, self).unlink()

    def _appraisal_plan_post(self):
        odoobot = self.env.ref('base.partner_root')
        dates = self.employee_id.sudo()._upcoming_appraisal_creation_date()
        for appraisal in self:
            # The only ongoing appraisal is the current one
            if not appraisal.appraisal_plan_posted and appraisal.company_id.appraisal_plan and appraisal.employee_id.sudo().ongoing_appraisal_count == 1:
                date = dates[appraisal.employee_id.id]
                formated_date = format_date(self.env, date, date_format="MMM d y")
                body = self.env._('Thanks to your Appraisal Plan, without any new manual Appraisal, the new Appraisal will be automatically created on %s.', formated_date)
                appraisal._message_log(body=body, author_id=odoobot.id)
                appraisal.appraisal_plan_posted = True

    def _generate_activities(self):
        today = fields.Date.context_today(self)
        for appraisal in self:
            employee = appraisal.employee_id
            managers = appraisal.manager_ids
            last_appraisal_date = employee.last_appraisal_id.date_close
            last_appraisal_months = last_appraisal_date and (
                today.year - last_appraisal_date.year) * 12 + (today.month - last_appraisal_date.month)
            if employee.user_id:
                # an appraisal has been just created
                if employee.appraisal_count == 1:
                    months = (appraisal.date_close.year - employee.create_date.year) * \
                        12 + (appraisal.date_close.month - employee.create_date.month)
                    note = self.env._("You arrived %s months ago. Your appraisal is created and you can fill it here.", months)
                else:
                    note = self.env._("Your last appraisal was %s months ago. Your appraisal is created and you can fill it here.", last_appraisal_months)
                appraisal.with_context(mail_activity_quick_update=True).activity_schedule(
                    'mail.mail_activity_data_todo', today,
                    summary=self.env._('Appraisal to fill'),
                    note=note, user_id=employee.user_id.id)
                for manager in managers.filtered('user_id'):
                    if employee.appraisal_count == 1:
                        note = self.env._(
                            "The employee %(employee)s arrived %(months)s months ago. The appraisal is created and you can fill it here.",
                            employee=employee._get_html_link(), months=months)
                    else:
                        note = self.env._(
                            "The last appraisal of %(employee)s was %(months)s months ago. The appraisal is created and you can fill it here.",
                            employee=appraisal.employee_id._get_html_link(), months=last_appraisal_months)
                    appraisal.with_context(mail_activity_quick_update=True).activity_schedule(
                        'mail.mail_activity_data_todo', today,
                        summary=self.env._('Appraisal for %s to fill', employee.name),
                        note=note, user_id=manager.user_id.id)

    @api.ondelete(at_uninstall=False)
    def _unlink_if_new_or_cancel(self):
        if any(appraisal.state != '1_new' for appraisal in self):
            raise UserError(self.env._("Oops! You can only delete draft appraisals."))

    def read(self, fields=None, load='_classic_read'):
        fields = fields or []
        check_feedback = set(fields) & {"manager_feedback", "employee_feedback"}
        check_notes = set(fields) & self._read_manager_only_fields()
        if check_feedback:
            fields = fields + ['can_see_employee_publish', 'can_see_manager_publish', 'employee_feedback_published', 'manager_feedback_published']
        if check_notes:
            fields = fields + ['employee_id']
        records = super().read(fields, load)
        for appraisal in records:
            employee_id = appraisal.get("employee_id")
            if isinstance(employee_id, (list, tuple)):
                # For some reason employee_id is a tuple if this method is called through JSON2
                employee_id = employee_id[0]
            if employee_id in self.env.user.employee_ids.ids:
                for field in appraisal.keys() & self._read_manager_only_fields():
                    appraisal[field] = False
        return records

    def action_calendar_event(self):
        self.ensure_one()
        partners = self.manager_ids.work_contact_id | self.employee_id.work_contact_id | self.env.user.partner_id
        action = self.env["ir.actions.actions"]._for_xml_id("calendar.action_calendar_event")
        action['context'] = {
            'default_partner_ids': partners.ids,
            'default_res_model': 'hr.appraisal',
            'default_res_id': self.id,
            'default_name': self.env._('Appraisal of %s', self.employee_id.name),
            'initial_date': self.date_close,
        }
        action['domain'] = [('partner_ids', 'in', partners.ids)]
        return action

    def _notification(self, title, message, msg_type, next_action):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'type': msg_type,
                'next': next_action,
            }
        }

    def action_confirm(self):
        appraisals_to_confirm = self.filtered(lambda r: r.state == '1_new')
        appraisals_to_confirm.write({'state': '2_pending'})

        if len(self) == 1:
            return

        next_action = {'type': 'ir.actions.client', 'tag': 'soft_reload'}

        if self - appraisals_to_confirm:
            next_action = self._notification(
                self.env._('Already Processed'),
                self.env._(
                    'Some appraisals were already in another state and were skipped.'
                ),
                'warning',
                next_action,
            )

        return next_action

    def action_done(self):
        self.state = '3_done'

    def action_back(self):
        appraisals_to_reset = self.filtered(lambda r: r.state == '2_pending')

        if appraisals_to_reset:
            appraisals_to_reset.write({
                'state': '1_new',
                'assessment_note': False,
            })
        if len(self) == 1:
            return

        action = {'type': 'ir.actions.client', 'tag': 'soft_reload'}

        if self - appraisals_to_reset:
            action = self._notification(
                self.env._('Warning'),
                self.env._(
                    'Some appraisals were already in another state and were skipped.'
                ),
                'warning',
                action,
            )

        return action

    def action_reopen(self):
        self.state = '2_pending'

    def action_open_employee_appraisals(self):
        view_id = self.env.ref('hr_appraisal.hr_appraisal_view_tree_orderby_create_date').id
        return {
            'name': self.env._('Previous Appraisals'),
            'res_model': 'hr.appraisal',
            'view_mode': 'kanban,list,form,gantt,calendar,activity',
            'views': [(False, 'kanban'), (view_id, 'list'), (False, 'form'), (False, 'gantt'), (False, 'calendar'), (False, 'activity')],
            'domain': [('employee_id', 'in', self.employee_id.ids)],
            'type': 'ir.actions.act_window',
            'target': 'current',
            'context': {
                'search_default_groupby_date_close': True,
                'hide_campaign_button': True,
            }
        }

    def action_open_goals(self):
        self.ensure_one()
        return {
            'name': self.env._("%s's Goals", self.employee_id.name),
            'view_mode': 'kanban,list,form,graph',
            'res_model': 'hr.appraisal.goal',
            'type': 'ir.actions.act_window',
            'views': [
                (self.env.ref('hr_appraisal.hr_appraisal_goal_view_tree').id, 'list'),
                (False, 'kanban'),
                (self.env.ref('hr_appraisal.hr_appraisal_goal_view_form').id, 'form'),
                (False, 'graph'),
            ],
            'target': 'current',
            'domain': [('employee_ids', '=', self.employee_id.id), ('child_ids', '=', False)],
            'context': {'default_employee_ids': self.employee_id.ids},
        }

    def action_send_appraisal_request(self):
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'request.appraisal',
            'target': 'new',
            'name': self.env._('Appraisal Request'),
            'context': {'default_appraisal_id': self.id},
        }

    def action_open_appraisal_campaign_wizard(self):
        employee_ids = False
        if self.env.context.get('active_model') == 'hr.employee':
            employee_ids = self.env.context.get('active_ids')
        elif self.env.context.get('active_model') == 'hr.appraisal':
            appraisals = self.env['hr.appraisal'].browse(self.env.context.get('active_ids'))
            employee_ids = appraisals.employee_id.ids
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Appraisal Campaign'),
            'res_model': 'hr.appraisal.campaign.wizard',
            'view_mode': 'form',
            'context': {
                'default_mode': 'employee',
                'default_employee_ids': employee_ids,
            },
            'target': 'new',
        }

    def action_open_feedback_popup(self):
        self.ensure_one()
        feedback_type = self.env.context.get('feedback_type', 'employee')
        view_title = self.env._("Employee's Feedback") if feedback_type == 'employee' else self.env._("Manager's Feedback")

        return {
            'name': view_title,
            'type': 'ir.actions.act_window',
            'res_model': 'hr.appraisal',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('hr_appraisal.view_hr_appraisal_feedback_popup').id,
            'target': 'new',
            'context': dict(self.env.context),
        }

    def _has_demo_data(self):
        if not self.env.user.has_group("hr_appraisal.group_hr_appraisal_user"):
            return True
        # This record only exists if the scenario has been already launched
        goal_tag = self.env.ref('hr_appraisal.hr_appraisal_goal_tag_softskills', raise_if_not_found=False)
        if goal_tag:
            return True
        return bool(self.env['ir.module.module'].search_count([
            '&',
                ('state', 'in', ['installed', 'to upgrade', 'uninstallable']),
                ('demo', '=', True)
        ]))

    def _load_demo_data(self):
        if self._has_demo_data():
            return
        env_sudo = self.sudo().with_context({}).env
        env_sudo['hr.employee']._load_scenario()
        convert.convert_file(env_sudo, 'hr_appraisal', 'data/scenarios/hr_appraisal_scenario.xml', None, mode='init')
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
