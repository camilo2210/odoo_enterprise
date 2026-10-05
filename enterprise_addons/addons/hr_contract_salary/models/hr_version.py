# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from markupsafe import Markup
from datetime import datetime, time

from odoo.addons.hr_contract_salary.utils.hr_version import requires_hr_version_context
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class HrVersion(models.Model):
    _inherit = 'hr.version'

    def _default_get_template_warning(self):
        sign_template_count = self.env['sign.template'].sudo().search_count([('active', '=', True)], limit=1)
        return not sign_template_count and _('No templates are configured yet. Do you want to set up first one?')

    origin_version_id = fields.Many2one(
        'hr.version', string="Origin Contract", domain="[('company_id', '=', company_id)]",
        groups="hr.group_hr_user", help="The contract from which this contract has been duplicated.", tracking=1)
    is_origin_contract_template = fields.Boolean(
        compute='_compute_is_origin_contract_template', string='Is origin contract a contract template?',
        groups="hr.group_hr_user", readonly=True)
    hash_token = fields.Char('Created From Token', groups="hr.group_hr_user", tracking=1)
    applicant_id = fields.Many2one('hr.applicant', groups="hr.group_hr_user",
                                   domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]", tracking=1)
    contract_reviews_count = fields.Integer(compute="_compute_contract_reviews_count",
                                            string="Proposed Contracts Count")
    contract_template_id = fields.Many2one(default=lambda self: self.job_id.contract_template_id or False)
    sign_template_id = fields.Many2one(
        'sign.template', compute='_compute_sign_template_id', readonly=False, store=True, copy=True,
        string="New Contract Template", groups="hr.group_hr_user",
        help="Default document that the applicant will have to sign to accept a contract offer.")
    sign_template_signatories_ids = fields.One2many('hr.contract.signatory', 'contract_template_id',
                                                    compute="_compute_sign_template_signatories_ids", store=True,
                                                    readonly=False, groups="hr.group_hr_user")
    contract_update_template_id = fields.Many2one(
        'sign.template', string="Contract Update", groups="hr.group_hr_user",
        compute='_compute_contract_update_template_id', store=True, readonly=False, copy=True,
        help="Default document that the employee will have to sign to update his contract.")
    contract_update_signatories_ids = fields.One2many('hr.contract.signatory', 'update_contract_template_id',
                                                      compute="_compute_contract_update_signatories_ids", store=True,
                                                      readonly=False, groups="hr.group_hr_user")
    signatures_count = fields.Integer(compute='_compute_signatures_count', string='# Signatures',
        help="The number of signatures on the pdf contract with the most signatures.", groups="hr.group_hr_user")
    image_1920_filename = fields.Char(groups="hr.group_hr_user", tracking=1)
    image_1920 = fields.Image(related='employee_id.image_1920', groups="hr.group_hr_manager", readonly=False)
    salary_offer_ids = fields.One2many('hr.contract.salary.offer', 'employee_version_id', groups="hr.group_hr_manager", tracking=1)
    originated_offer_id = fields.Many2one('hr.contract.salary.offer', help="The original offer",
                                          groups="hr.group_hr_user", tracking=1)
    template_warning = fields.Char(default=_default_get_template_warning, store=False, groups="hr.group_hr_user")

    @api.constrains('sign_template_signatories_ids')
    def _check_signatories_unicity(self):
        for version in self:
            roles = [i.sign_role_id for i in version.sign_template_signatories_ids]
            if len(roles) != len(set(roles)):
                raise ValidationError(_("You cannot have multiple person responsible for the same role on contract signature template."))

    @api.constrains('contract_update_signatories_ids')
    def _check_update_signatories_unicity(self):
        for version in self:
            roles = [i.sign_role_id for i in version.contract_update_signatories_ids]
            if len(roles) != len(set(roles)):
                raise ValidationError(_("You cannot have multiple person responsible for the same role on contract update signature template."))

    @api.depends('sign_template_id')
    def _compute_sign_template_signatories_ids(self):
        for version in self:
            version.sign_template_signatories_ids = self.env['hr.contract.signatory'].create_empty_signatories(version.sign_template_id)

    @api.depends('contract_update_template_id')
    def _compute_contract_update_signatories_ids(self):
        for version in self:
            version.contract_update_signatories_ids = self.env['hr.contract.signatory'].create_empty_signatories(version.contract_update_template_id)

    @api.constrains('hr_responsible_id', 'sign_template_id')
    def _check_hr_responsible_id(self):
        for version in self:
            if version.sign_template_id:
                if not version.hr_responsible_id.has_group('sign.group_sign_user'):
                    raise ValidationError(_("HR Responsible %s should be a user of Sign when New Contract Document Template is specified", version.hr_responsible_id.name))
                if not version.hr_responsible_id.email_formatted:
                    raise ValidationError(_("HR Responsible %s should have a valid email address when New Contract Document Template is specified", version.hr_responsible_id.name))

    @api.depends('origin_version_id')
    def _compute_is_origin_contract_template(self):
        for version in self:
            version.is_origin_contract_template = version.origin_version_id and not version.origin_version_id.employee_id

    @api.depends('company_id', 'job_id')
    def _compute_structure_type_id(self):
        versions = self.env['hr.version']
        for version in self:
            if version.job_id and version.job_id.contract_template_id and version.job_id.contract_template_id.structure_type_id:
                version.structure_type_id = version.job_id.contract_template_id.structure_type_id
            else:
                versions |= version
        super(HrVersion, versions)._compute_structure_type_id()

    @api.depends('sign_request_ids.nb_closed')
    def _compute_signatures_count(self):
        for version in self:
            version.signatures_count = max(version.sign_request_ids.mapped('nb_closed') or [0])

    @api.depends('origin_version_id')
    def _compute_contract_reviews_count(self):
        data = dict(self.with_context(active_test=False)._read_group(
            [('origin_version_id', 'in', self.ids)],
            ['origin_version_id'],
            ['__count'],
        ))
        for version in self:
            version.contract_reviews_count = data.get(version, 0)

    @api.depends('contract_template_id')
    def _compute_sign_template_id(self):
        for version in self:
            if version.contract_template_id:
                version.sign_template_id = version.contract_template_id.sign_template_id

    @api.depends('contract_template_id')
    def _compute_contract_update_template_id(self):
        for version in self:
            if version.contract_template_id and version.id != version.contract_template_id.id:
                version.contract_update_template_id = version.contract_template_id.contract_update_template_id

    def action_show_contract_reviews(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "hr.version",
            "views": [[False, "list"], [False, "form"]],
            "domain": [["origin_version_id", "=", self.id]],
            "context": {"active_test": False},
            "name": "Contracts Reviews",
        }

    def action_generate_offer(self):

        offer_validity_period = self.env['ir.config_parameter'].sudo().get_int(
            'hr_contract_salary.employee_salary_simulator_link_validity') or 30
        offer_values = self._get_offer_values()
        offer_values['validity_days_count'] = offer_validity_period
        offer = self.env['hr.contract.salary.offer'].with_context(
            default_contract_template_id=self.id).create(offer_values)

        self.message_post(
            body=_("An %(offer)s has been sent by %(user)s to the employee (mail: %(email)s)",
                    offer=Markup("<a href='#' data-oe-model='hr.contract.salary.offer' data-oe-id='{offer_id}'>Offer</a>")
                    .format(offer_id=offer.id),
                    user=self.env.user.name,
                    email=self.employee_id.work_email
            )
        )

        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'hr.contract.salary.offer',
            'res_id': offer.id,
            'views': [(False, 'form')],
            'context': {'active_model': 'hr.version', 'default_employee_version_id': self.id}
        }

    def _get_offer_values(self):
        self.ensure_one()
        return {
            'company_id': self.company_id.id,
            'contract_template_id': self.id,
            'employee_version_id': self.id,
            'final_yearly_costs': self.final_yearly_costs,
            'salary_amount': self.final_yearly_costs,
            'budget_type': 'yearly_employer',
            'job_title': self.job_id.name,
            'employee_job_id':  self.job_id.id,
            'department_id': self.department_id.id,
        }

    def _get_values_dict(self):
        self.ensure_one()
        return self.read(load=None)[0]

    def send_offer(self):
        self.ensure_one()
        try:
            template_id = self.env.ref('hr_contract_salary.mail_template_send_offer').id
        except ValueError:
            template_id = False
        path = '/salary_package/contract/' + str(self.id)
        ctx = {
            'default_email_layout_xmlid': 'mail.mail_notification_light',
            'default_model': 'hr.version',
            'default_res_ids': self.ids,
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'salary_package_url': self.env['hr.version'].get_base_url() + path,
        }
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [[False, 'form']],
            'target': 'new',
            'context': ctx,
        }

    def action_archive(self):
        res = super().action_archive()
        job_positions = self.env['hr.job'].search([('contract_template_id', 'in', self.ids)])
        job_positions.contract_template_id = False
        return res

    @requires_hr_version_context()
    def _generate_salary_simulation_payslip(self):
        self.ensure_one()
        payslip = self.env['hr.payslip'].sudo().create({
            'employee_id': self.employee_id.id,
            'version_id': self.id,
            'struct_id': self.structure_type_id.default_struct_id.id,
            'company_id': self.employee_id.company_id.id,
        })

        work_days_data = self.employee_id._get_work_days_data_batch(
            datetime.combine(payslip.date_from, time.min), datetime.combine(payslip.date_to, time.max),
            compute_leaves=False, calendar=self.resource_calendar_id,
        )[self.employee_id.id]
        payslip.worked_days_line_ids = self.env['hr.payslip.worked_days'].sudo().create({
            'payslip_id': payslip.id,
            'version_id': self.id,
            'work_entry_type_id': self._get_default_work_entry_type_id(),
            'number_of_days': work_days_data.get('days', 0),
            'number_of_hours': work_days_data.get('hours', 0),
        })

        # Part Time Simulation
        old_wage = payslip.version_id.wage
        new_payslip_vals = {}
        if self.env.context.get("simulation_working_schedule"):
            working_schedule = self.env.context.get("simulation_working_schedule", '100')
            old_calendar = payslip.version_id.company_id.resource_calendar_id
            new_calendar = self.env['resource.calendar']
            if working_schedule == '100':
                pass
            elif working_schedule == '90':
                new_calendar = old_calendar.copy({'global_leave_ids': False})
                new_calendar.attendance_ids[:1].unlink()
            elif working_schedule == '80':
                new_calendar = old_calendar.copy({'global_leave_ids': False})
                new_calendar.attendance_ids[:2].unlink()
            elif working_schedule == '60':
                new_calendar = old_calendar.copy({'global_leave_ids': False})
                new_calendar.attendance_ids[:4].unlink()
            elif working_schedule == '50':
                new_calendar = old_calendar.copy({'global_leave_ids': False})
                new_calendar.attendance_ids[:5].unlink()
            elif working_schedule == '40':
                new_calendar = old_calendar.copy({'global_leave_ids': False})
                new_calendar.attendance_ids[:6].unlink()
            elif working_schedule == '20':
                new_calendar = old_calendar.copy({'global_leave_ids': False})
                new_calendar.attendance_ids[:8].unlink()
            new_wage = old_wage * int(working_schedule) / 100.0
            is_full_time = working_schedule == '100'
            new_payslip_vals.update({
                'resource_calendar_id': new_calendar.id,
                'wage': new_wage,
            })

        else:
            is_full_time = True

        payslip = payslip.with_context(
            is_simulation_offer=True,
            salary_simulation=True,
            salary_simulation_full_time=is_full_time,
            salary_simulation_full_time_yearly_cost=self.final_yearly_costs,
            origin_version_id=self.env.context.get('origin_version_id', False),
            lang=None
        )

        if not is_full_time:
            payslip.version_id.write(new_payslip_vals)

        return payslip
