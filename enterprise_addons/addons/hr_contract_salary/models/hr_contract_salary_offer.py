# Part of Odoo. See LICENSE file for full copyright and licensing details.
import uuid
from collections import defaultdict
from dateutil.relativedelta import relativedelta
from datetime import date
from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.addons.hr_contract_salary.utils.hr_version import requires_hr_version_context, hr_version_context
from werkzeug.urls import url_encode
from odoo.exceptions import UserError
from odoo.tools import float_compare


class HrContractSalaryOffer(models.Model):
    _name = 'hr.contract.salary.offer'
    _description = 'Salary Package Offer'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    @api.model
    def default_get(self, fields):
        result = super().default_get(fields)
        version_id = result.get('employee_version_id')
        if version_id:
            version = self.env['hr.version'].browse(version_id)
            result['employee_id'] = version.employee_id.id
        for field in fields:
            if field == 'access_token' and 'applicant_id' in result:
                result['access_token'] = uuid.uuid4().hex
            if field.startswith('x_') and 'active_id' in self.env.context:
                model = self.env.context.get('active_model')
                if model == "hr.version" and field in self.env[model]:
                    version = self.env[model].browse(self.env.context['active_id'])
                    result[field] = version[field]
                elif model == "hr.applicant" and field in self.env["hr.version"] and "default_contract_template_id" in self.env.context:
                    version = self.env["hr.version"].browse(self.env.context['default_contract_template_id'])
                    result[field] = version[field]
        if self.env.context.get('default_is_simulation_offer'):
            result['access_token'] = uuid.uuid4().hex
        return result

    def _get_default_struct_id(self):
        return self.env['hr.version']._default_salary_structure().default_struct_id

    def _get_default_resource_calendar_id(self):
        return self.env.company.resource_calendar_id

    display_name = fields.Char(string="Title", compute="_compute_display_name", readonly=False, store=True)
    company_id = fields.Many2one(
        'res.company',
        string="Company",
        compute="_compute_company_id",
        store=True,
        index=True,
        default=lambda self: self.env.company.id,
    )
    currency_id = fields.Many2one(related='company_id.currency_id')
    contract_template_id = fields.Many2one(
        'hr.version', compute="_compute_contract_template_id", store=True, index='btree_not_null', check_company=True, readonly=False,
        domain="['|', ('employee_id', '=', False), ('id', '=', employee_version_id)]", tracking=True)
    sign_template_id = fields.Many2one(
        'sign.template', compute='_compute_sign_template_id', readonly=False, store=True, string="PDF Sign Template",
        help="Default document that the applicant will have to sign to accept a contract offer.")
    sign_template_signatories_ids = fields.One2many(
        'hr.contract.signatory', 'offer_id', compute="_compute_sign_template_signatories_ids",
        store=True, readonly=False)
    state = fields.Selection([
        ('open', 'In Progress'),
        ('half_signed', 'Partially Signed'),
        ('full_signed', 'Fully Signed'),
        ('expired', 'Expired'),
        ('refused', 'Refused'),
        ('cancelled', 'Cancelled'),
    ], default='open', tracking=True)
    refusal_reason = fields.Many2one('hr.contract.salary.offer.refusal.reason', string="Refusal Reason", tracking=True)
    offer_create_date = fields.Date("Offer Create Date", compute="_compute_offer_create_date", readonly=True)
    refusal_date = fields.Date("Refusal Date")
    sign_request_ids = fields.Many2many('sign.request', string='Requested Signatures')
    employee_version_id = fields.Many2one('hr.version', tracking=True,
        store=True, compute="_compute_employee_version_id", inverse='_inverse_employee_version_id',
        index='btree_not_null')
    employee_id = fields.Many2one('hr.employee', check_company=True, tracking=True)
    applicant_id = fields.Many2one('hr.applicant', index=True, tracking=True)
    applicant_name = fields.Char(related='applicant_id.partner_name')
    final_yearly_costs = fields.Monetary("Employer Budget", aggregator="avg", store=True, tracking=True,
        compute="_compute_final_yearly_costs")
    budget_type = fields.Selection(
        selection=[('monthly_gross', 'Gross Per Month'), ('yearly_employer', 'Yearly Employer Cost'), ('monthly_net', 'Net Per Month')],
        default='yearly_employer',
        required=True
    )
    job_title = fields.Char(tracking=True, store=True, readonly=False,
        compute="_compute_offer_values_from_template")
    employee_job_id = fields.Many2one('hr.job', tracking=True, store=True, index=True, readonly=False,
        compute="_compute_offer_values_from_template")
    department_id = fields.Many2one('hr.department', tracking=True, store=True, readonly=False,
        compute="_compute_offer_values_from_template")
    contract_start_date = fields.Date(tracking=True, default=fields.Date.context_today, required=True,
        help="For employees, The contract start date determines whether this offer creates a new contract or amends an existing one. If the selected start date falls within the period of an existing contract for the employee, it will be treated as an amendment rather than a new contract.")
    contract_end_date = fields.Date(tracking=True, store=True, compute="_compute_contract_end_date", readonly=False)
    access_token = fields.Char('Access Token', copy=False, tracking=True, store=True, compute="_compute_token")
    validity_days_count = fields.Integer("Validity Days Count",
                              compute="_compute_validity_days_count",
                              store=True, readonly=False)
    offer_end_date = fields.Date('Offer Expiration', readonly=False,
                                 copy=False, tracking=True)
    url = fields.Char('Link', compute='_compute_url')
    is_half_sign_state_required = fields.Boolean(
        compute="_compute_is_half_sign_state_required",
        compute_sudo=True,
        export_string_translation=False
    )
    has_sign_template = fields.Boolean(compute="_compute_has_sign_template")
    is_simulation_offer = fields.Boolean()
    salary_amount = fields.Monetary(string="Salary", compute='_compute_salary_amount_from_template', store=True, readonly=False)
    country_id = fields.Many2one(related='company_id.country_id')
    country_code = fields.Char(related='country_id.code', depends=['country_id'])
    structure_id = fields.Many2one(
        'hr.payroll.structure',
        store=True,
        compute="_compute_structure_values_from_template",
        index=True,
        readonly=False,
        string="Pay Structure",
        default=_get_default_struct_id,
        domain="[('country_id', 'in', (country_id, False))]",
    )
    structure_type_id = fields.Many2one(related='structure_id.type_id')
    resource_calendar_id = fields.Many2one(
        'resource.calendar',
        store=True,
        compute="_compute_structure_values_from_template",
        readonly=False,
        string="Working Schedule",
        check_company=True
    )
    gross_wage = fields.Monetary(compute='_compute_salary', store=True)
    net_wage = fields.Monetary(compute='_compute_salary', store=True)
    monthly_benefits = fields.Monetary(compute='_compute_salary', store=True)
    yearly_benefits = fields.Monetary(compute='_compute_salary', store=True)
    yearly_employer_cost = fields.Monetary(compute='_compute_salary', store=True)
    monthly_employer_cost = fields.Monetary(compute='_compute_salary', store=True)
    work_time_rate = fields.Float(compute='_compute_salary', string='Work Time Rate', store=True)

    has_any_template = fields.Boolean(compute="_compute_has_any_template")
    is_contract_amendment = fields.Boolean(compute="_compute_is_contract_amendment")
    future_version_date = fields.Date(compute='_compute_future_version_date')

    _check_dates_validity = models.Constraint(
        "CHECK(contract_end_date IS NULL OR contract_start_date <= contract_end_date)",
        "The contract start date cannot be after the contract end date."
    )

    def _compute_has_any_template(self):
        self.has_any_template = bool(self.env['sign.template'].search_count([], limit=1))

    @requires_hr_version_context()
    def _get_version(self):
        self.ensure_one()
        if self.state == 'half_signed':
            if self.employee_id:
                archived_versions = self.employee_id.with_context(active_test=False).version_ids.filtered(lambda emp: not emp.active).sorted("create_date")
            else:
                archived_versions = self.env['hr.version'].with_context(active_test=False).search([
                    ('applicant_id', '=', self.applicant_id.id),
                    ('active', '=', False)
                ]).sorted("create_date")
            final_version = archived_versions[-1]
        else:
            employee = self.employee_id or self.env['hr.employee'].with_user(SUPERUSER_ID).sudo().create({
                'name': self.applicant_id.partner_name if self.applicant_id else 'Simulation Employee',
                'private_phone': self.applicant_id.partner_phone if self.applicant_id else False,
                'private_email': self.applicant_id.email_from if self.applicant_id else False,
                'active': False,
                'country_id': self.company_id.country_id.id,
                'private_country_id': self.company_id.country_id.id,
                'certificate': False,  # To force encoding it
                'company_id': self.company_id.id,
            })
            if self.contract_template_id:
                employee.version_id.write(
                    self.env['hr.version'].get_values_from_contract_template(self.contract_template_id)
                )
            final_version = employee.current_version_id

        version_vals = {}
        resource_calendar = self.resource_calendar_id or final_version.resource_calendar_id or self._get_default_resource_calendar_id()
        if self.is_simulation_offer:
            if self.employee_id:
                final_version = self.employee_id.version_id
            version_vals.update({
                'structure_type_id': self.structure_id.type_id.id,
            })
        monthly_wage = max(0, final_version._get_wage_from_yearly_costs(self.final_yearly_costs))
        version_vals.update({
            'resource_calendar_id': resource_calendar.id,
            final_version._get_contract_wage_field(): monthly_wage,
            'wage': monthly_wage,
        })
        if self.is_simulation_offer:
            work_time_rate = resource_calendar.work_time_rate
            new_wage = monthly_wage * work_time_rate
            version_vals.update({
                'wage': new_wage,
            })
        employee = final_version.employee_id
        if employee and employee.active:
            self.with_context(tracking_disable=True)._archive_future_versions(version=employee.version_id)
        final_version.write(version_vals)
        return final_version

    @api.depends('salary_amount', 'budget_type')
    def _compute_final_yearly_costs(self):
        final_yearly_costs_by_offer = {}
        with hr_version_context(self, invalidate=True) as offers:
            for offer in offers.with_context(is_simulation_offer=True).filtered(lambda o: o.budget_type != 'yearly_employer'):
                version = offer._get_version()
                gross = offer.salary_amount
                if offer.budget_type == 'monthly_net':
                    MAX_ITERATIONS, ERROR_MARGIN, VELOCITY = 100, 0.01, 1.5
                    payslip = version._generate_salary_simulation_payslip()

                    def get_net_error(gross):
                        version.update({version._get_contract_wage_field(): gross, 'wage': gross})
                        net_amount = sum(line['total'] for line in payslip._get_payslip_lines() if line['code'] == 'NET')
                        return net_amount - offer.salary_amount

                    it, lambd = 0, 0.01
                    while float_compare(error := get_net_error(gross), 0, precision_rounding=ERROR_MARGIN) != 0 and it < MAX_ITERATIONS:
                        df = (get_net_error(gross + 1) - get_net_error(gross - 1)) / 2
                        if float_compare(abs(df), 0.5, precision_rounding=1e-5) > 0:
                            lambd *= VELOCITY
                        else:
                            lambd /= VELOCITY
                        gross = gross - error / (df + lambd)
                        it += 1
                final_yearly_costs_by_offer[offer] = version._get_employer_costs_from_gross(gross)

        for offer in self:
            offer.final_yearly_costs = final_yearly_costs_by_offer.get(offer, offer.salary_amount)
        for field in ['work_time_rate', 'gross_wage', 'net_wage', 'monthly_benefits', 'yearly_benefits', 'yearly_employer_cost', 'monthly_employer_cost']:
            self.env.add_to_compute(self._fields[field], self)

    @api.depends('salary_amount', 'budget_type', 'structure_id', 'resource_calendar_id')
    def _compute_salary(self) -> None:
        vals_by_offer = {}
        with hr_version_context(self, invalidate=True) as offers:
            for offer in offers:
                version = offer._get_version()
                payslip = version._generate_salary_simulation_payslip()
                payslip_lines = payslip._get_payslip_lines()
                yearly_employer_cost = offer.final_yearly_costs
                if offer.is_simulation_offer:
                    yearly_employer_cost = version._get_employer_costs_from_gross(version._get_contract_wage())
                monthly_benefits, yearly_benefits = offer._get_benefits(version)
                gross_line_amount = sum(line['total'] for line in payslip_lines if line['code'] == 'BASIC')
                net_line_amount = sum(line['total'] for line in payslip_lines if line['code'] == 'NET')
                vals_by_offer[offer] = {
                    'work_time_rate': version.work_time_rate,
                    'gross_wage': gross_line_amount,
                    'net_wage': net_line_amount,
                    'monthly_benefits': monthly_benefits,
                    'yearly_benefits': yearly_benefits,
                    'yearly_employer_cost': yearly_employer_cost,
                    'monthly_employer_cost': round(yearly_employer_cost / 12, 2),
                    'resource_calendar_id': version.resource_calendar_id.id,
                }

        for offer in self:
            offer.update(vals_by_offer[offer])

    @api.depends('contract_template_id.sign_template_id', 'contract_template_id.contract_update_template_id')
    def _compute_has_sign_template(self):
        for offer in self:
            if offer.employee_id and offer.employee_id.active:
                offer.has_sign_template = offer.contract_template_id.contract_update_template_id
            else:
                offer.has_sign_template = offer.contract_template_id.sign_template_id

    @api.depends('contract_template_id.sign_template_id', 'contract_template_id.contract_update_template_id')
    def _compute_sign_template_id(self):
        for offer in self:
            if offer.contract_template_id:
                if offer.employee_id and offer.employee_id.active:
                    sign_template = offer.contract_template_id.contract_update_template_id
                else:
                    sign_template = offer.contract_template_id.sign_template_id

                # Update only if a template exists; otherwise, keep the current value
                if sign_template:
                    offer.sign_template_id = sign_template

    def _get_benefits(self, version):
        monthly_benefit_category = self.env.ref('hr_contract_salary.hr_contract_salary_resume_category_monthly_benefits')
        yearly_benefit_category = self.env.ref('hr_contract_salary.hr_contract_salary_resume_category_yearly_benefits')
        resume_lines = self.env['hr.contract.salary.resume'].sudo().with_company(version.company_id).search([
            '|',
            ('structure_type_id', '=', False),
            ('structure_type_id', '=', version.structure_type_id.id),
            ('value_type', '=', 'sum'),
            ('category_id', 'in', (monthly_benefit_category.id, yearly_benefit_category.id))
        ])
        result = defaultdict(int)
        for resume_line in resume_lines:
            value = 0
            for benefit in resume_line.benefit_ids:
                if not benefit.fold_field or (benefit.fold_field and version[benefit.fold_field]):
                    field = benefit.field
                    value += version[field] if benefit.source == 'field' else version._get_property_input_value(benefit.salary_rule_id.code)
            result[resume_line.category_id.id] += round(float(value), 2)
        return result[monthly_benefit_category.id], result[yearly_benefit_category.id]

    def _copy_contract_template_signatories(self):
        self.ensure_one()
        if self.employee_id and self.employee_id.active:
            contract_template_signatories_copy = self.contract_template_id.contract_update_signatories_ids.copy()
        else:
            contract_template_signatories_copy = self.contract_template_id.sign_template_signatories_ids.copy()
        # Must unlink the signatory from the contract template, will be linked to the offer with the SET command
        contract_template_signatories_copy.contract_template_id = False
        contract_template_signatories_copy.update_contract_template_id = False
        return [(5, 0, 0)] + [(6, 0, contract_template_signatories_copy.ids)]

    @api.depends('sign_template_id', 'contract_template_id', 'has_sign_template')
    def _compute_sign_template_signatories_ids(self):
        for offer in self:
            if offer.contract_template_id and offer.has_sign_template:
                offer.sign_template_signatories_ids = offer._copy_contract_template_signatories()
            else:
                offer.sign_template_signatories_ids = self.env['hr.contract.signatory'].create_empty_signatories(offer.sign_template_id)

    @api.depends('contract_template_id.sign_template_signatories_ids')
    def _compute_is_half_sign_state_required(self):
        for offer in self:
            offer.is_half_sign_state_required = len(offer.sign_template_signatories_ids) != 1

    @api.depends("access_token", "final_yearly_costs")
    def _compute_url(self):
        base_url = self.env['hr.contract.salary.offer'].get_base_url()
        for offer in self:
            offer.url = base_url \
                      + f"/salary_package/simulation/offer/{offer._origin.id}" \
                      + f"?final_yearly_costs={round(offer.final_yearly_costs, 2)}" \
                      + (f"&token={offer.access_token}" if offer.access_token else "")

    @api.depends("employee_id", "applicant_id")
    def _compute_token(self):
        for offer in self:
            if not offer.access_token and (not offer.employee_id or not offer.employee_id.user_id):
                offer.access_token = uuid.uuid4().hex

    @api.depends('applicant_id', 'employee_version_id', 'employee_id')
    def _compute_display_name(self):
        for offer in self:
            if offer.applicant_id:
                name = offer.applicant_id.employee_id.name or \
                    offer.applicant_id.partner_id.name or \
                    offer.applicant_id.partner_name
            else:
                name = offer.employee_id.name
            offer.display_name = _("Offer for %(recipient)s", recipient=name) if name else ""

    @api.depends('create_date')
    def _compute_offer_create_date(self):
        today = fields.Date.context_today(self)
        for offer in self:
            offer.offer_create_date = offer.create_date and offer.create_date.date() or today

    @api.depends('offer_create_date', 'offer_end_date')
    def _compute_validity_days_count(self):
        for offer in self:
            offer.validity_days_count = (offer.offer_end_date - offer.offer_create_date).days \
                if offer.offer_end_date else False

    @api.depends('employee_id', 'applicant_id')
    def _compute_company_id(self):
        for offer in self:
            if offer.employee_id:
                offer.company_id = offer.employee_id.company_id
            elif offer.applicant_id:
                offer.company_id = offer.applicant_id.company_id
            else:
                offer.company_id = self.env.company.id

    @api.depends('state', 'employee_id', 'applicant_id', 'contract_start_date')
    def _compute_employee_version_id(self):
        today = fields.Date.context_today(self)
        for offer in self:
            employee = False
            if offer.employee_id:
                employee = offer.employee_id
            elif offer.applicant_id.employee_id and offer.state == 'full_signed':
                employee = offer.applicant_id.employee_id
            if employee:
                contract_start_date = offer.contract_start_date or today.replace(day=1)
                offer.employee_version_id = employee._get_version(contract_start_date)

    @api.depends('is_simulation_offer', 'employee_id')
    def _compute_contract_template_id(self):
        simulated_offers = self.filtered(lambda o: o.is_simulation_offer and o.employee_id)
        for offer in simulated_offers:
            offer.contract_template_id = offer.employee_id.version_id

        for offer in (self - simulated_offers):
            if not offer.applicant_id:
                offer.contract_template_id = offer.employee_id.version_id

    @api.depends('contract_template_id')
    def _compute_offer_values_from_template(self):
        for offer in self:
            if offer.state != 'open':
                continue
            if offer.contract_template_id:
                offer.job_title = offer.contract_template_id.job_id.name
                offer.employee_job_id = offer.contract_template_id.job_id
                offer.department_id = offer.contract_template_id.department_id
                offer.company_id = offer.contract_template_id.company_id
            else:
                offer.company_id = offer.env.company.id

    @api.depends('contract_template_id')
    def _compute_salary_amount_from_template(self):
        for offer in self.filtered(lambda o: o.contract_template_id and o.budget_type != 'monthly_net'):
            if offer.budget_type == 'monthly_gross':
                offer.salary_amount = offer.contract_template_id._get_contract_wage()
            else:
                offer.salary_amount = offer.contract_template_id.final_yearly_costs

        net_offers = self.filtered(lambda o: o.contract_template_id and o.budget_type == 'monthly_net')
        if net_offers:
            net_salaries_by_offer = {}
            with hr_version_context(net_offers) as simulated_offers:
                for offer in simulated_offers:
                    version = offer._get_version()
                    monthly_gross = version._get_wage_from_yearly_costs(offer.contract_template_id.final_yearly_costs)
                    version.update({version._get_contract_wage_field(): monthly_gross, 'wage': monthly_gross})
                    payslip = version._generate_salary_simulation_payslip()
                    net_salaries_by_offer[offer] = payslip._get_line_values(['NET'])['NET'][payslip.id]['total']

            for offer in net_offers:
                offer.salary_amount = net_salaries_by_offer.get(offer, 0.0)

    @api.depends('contract_template_id')
    def _compute_structure_values_from_template(self):
        for offer in self.filtered(lambda o: o.contract_template_id):
            offer.structure_id = offer.contract_template_id.structure_type_id.default_struct_id
            offer.resource_calendar_id = offer.contract_template_id.resource_calendar_id

    @api.depends('employee_version_id.contract_date_start', 'employee_version_id.contract_date_end', 'contract_start_date')
    def _compute_is_contract_amendment(self):
        today = fields.Date.context_today(self)
        for offer in self:
            contract_start_date = offer.contract_start_date or today.replace(day=1)
            offer.is_contract_amendment = (
                offer.employee_version_id
                and offer.employee_version_id.contract_date_start
                and offer.employee_version_id.contract_date_start <= contract_start_date
                and (
                    not offer.employee_version_id.contract_date_end
                    or offer.employee_version_id.contract_date_end >= contract_start_date
                )
            )

    @api.depends('employee_id.version_ids.date_start', 'contract_start_date', 'state')
    def _compute_future_version_date(self):
        today = fields.Date.context_today(self)
        for offer in self:
            if offer.employee_id and offer.state in ['open', 'half_signed']:
                contract_start_date = offer.contract_start_date or today.replace(day=1)
                offer.future_version_date = offer.employee_id.version_ids.filtered(
                    lambda v: v.date_start >= contract_start_date
                ).sorted("date_start")[:1].date_start
            else:
                offer.future_version_date = False

    @api.depends('is_contract_amendment', 'employee_version_id.contract_date_end')
    def _compute_contract_end_date(self):
        for offer in self:
            if offer.is_contract_amendment:
                offer.contract_end_date = offer.employee_version_id.contract_date_end

    def _inverse_employee_version_id(self):
        for offer in self:
            offer.employee_id = offer.employee_version_id.employee_id

    @api.onchange('employee_job_id')
    def _onchange_employee_job_id(self):
        self.job_title = self.employee_job_id.name
        if self.employee_job_id.department_id:
            self.department_id = self.employee_job_id.department_id

    @api.onchange('budget_type')
    def _onchange_budget_type(self):
        for offer in self.filtered(lambda o: o.is_simulation_offer):
            match offer.budget_type:
                case 'monthly_net':
                    offer.salary_amount = (offer._origin or offer).net_wage
                case 'monthly_gross':
                    offer.salary_amount = (offer._origin or offer).gross_wage
                case 'yearly_employer':
                    offer.salary_amount = (offer._origin or offer).yearly_employer_cost

    def action_open_refuse_wizard(self):
        action = self.env["ir.actions.actions"]._for_xml_id("hr_contract_salary.open_refuse_wizard")
        return {
            **action,
            'context': {
                'dialog_size': 'medium',
            },
        }

    def action_refuse_offer(self, message=None, refusal_reason=None):
        self.unlink_archived_version_offer()
        if not message:
            message = _("%s manually set the Offer to Refused", self.env.user.name)
        self.write({
            'state': 'refused',
            'refusal_reason': refusal_reason,
            'refusal_date': fields.Date.context_today(self)
        })
        for offer in self:
            offer.message_post(body=message)

    def action_jump_to_offer(self):
        self.ensure_one()
        url = f'/salary_package/simulation/offer/{self.id}'
        if self.access_token:
            url += '?' + url_encode({'token': self.access_token})
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }

    def action_regenerate_token(self):
        for offer in self:
            offer.access_token = uuid.uuid4().hex

    def unlink(self):
        self.unlink_archived_version_offer()
        # Delete the employee if it is archived and the number of offers of an
        # applicant to delete is equal to the number of offers linked to that applicant
        offers_with_archived_employee = self.filtered(lambda o: not o.applicant_id.employee_id.active)
        offers_by_applicant = offers_with_archived_employee.grouped('applicant_id')
        employee_to_unlink = self.env['hr.employee']
        for applicant, offers in offers_by_applicant.items():
            if len(offers) == applicant.salary_offers_count:
                employee_to_unlink |= applicant.employee_id
        employee_to_unlink.unlink()
        return super().unlink()

    def _cron_update_state(self):
        self.search([
            ('state', 'in', ['open', 'half_signed']),
            ('offer_end_date', '<', fields.Date.today()),
        ]).write({'state': 'expired'})

    def action_send_by_email(self):
        self.ensure_one()
        try:
            template_id = self.env.ref('hr_contract_salary.mail_template_send_offer').id
        except ValueError:
            template_id = False
        try:
            template_applicant_id = self.env.ref('hr_contract_salary.mail_template_send_offer_applicant').id
        except ValueError:
            template_applicant_id = False
        if self.applicant_id:
            default_template_id = template_applicant_id
        else:
            default_template_id = template_id

        ctx = {
            'default_composition_mode': 'comment',
            'default_model': 'hr.contract.salary.offer',
            'default_res_ids': self.ids,
            'default_template_id': default_template_id,
            'offer_id': self.id,
            'access_token': self.access_token,
            'validity_end': self.offer_end_date,
        }
        return {
            'name': self.env._("Send Offer"),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [[False, 'form']],
            'target': 'new',
            'context': ctx,
        }

    def action_view_signature_request(self):
        self.ensure_one()
        pending_sign_requests = self.sign_request_ids.filtered(lambda r: r.state != 'signed')
        if len(pending_sign_requests) == 1:
            return pending_sign_requests.go_to_document()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Signature Requests',
            'view_mode': 'kanban,list',
            'res_model': 'sign.request',
            'domain': [('id', 'in', pending_sign_requests.ids)]
        }

    def action_edit_offer_signatories(self):
        self.ensure_one()
        return {
            'name': self.env._("Edit PDF Template Signatories"),
            'type': 'ir.actions.act_window',
            'view_mode': 'list',
            'res_model': 'hr.contract.signatory',
            'target': 'new',
            'domain': [('id', 'in', self.sign_template_signatories_ids.ids)],
        }

    def action_view_version(self):
        self.ensure_one()
        version = (
            self.env['hr.version'].with_context(active_test=False).search([('originated_offer_id', '=', self.id)], order="active desc, id desc", limit=1)
            or self.employee_version_id
            or self.env['hr.version'].with_context(active_test=False).search([('applicant_id', '=', self.applicant_id.id)], order="active desc, id desc", limit=1)
        )
        if self.state == 'half_signed':
            action = self.env.ref('hr_contract_salary.action_view_partially_signed_contract_statbutton')._get_action_dict()
        else:
            action = self.env.ref('hr_contract_salary.action_view_contract_statbutton')._get_action_dict()

        action['res_id'] = self.employee_id.id or self.applicant_id.employee_id.id or version.employee_id.id
        action['context'] = {'version_id': version.id}
        return action

    def _mail_get_partners(self, introspect_fields=False):
        return {
            offer.id: (offer.applicant_id.partner_id + offer.employee_id.work_contact_id)
            for offer in self
        }

    def _mail_get_primary_email(self):
        # Override as there is no "_primary_email" defined here, it is a related
        return {
            record.id: record.applicant_id.email_from or record.employee_id.work_email
            for record in self
        }

    def unlink_archived_version_offer(self):
        archived_versions = self.env['hr.version'].search([
            ('originated_offer_id', 'in', self.ids),
            ('active', '=', False)
        ])
        if archived_versions:
            archived_versions.sign_request_ids.write({'state': 'canceled', 'active': False})
            archived_versions.unlink()

    @api.model
    def action_cron_remove_simulation_offers(self):
        simulation_offers = self.env['hr.contract.salary.offer'].search([('is_simulation_offer', '=', True)])
        older_than_one_month_offers = simulation_offers.filtered(
            lambda offer: offer.offer_create_date < (date.today() - relativedelta(month=1))
        )
        return older_than_one_month_offers.unlink()

    def action_open_salary_configurator(self):
        self.ensure_one()
        self.check_simulation_required_fields()
        self.resource_calendar_id = self.resource_calendar_id or self._get_default_resource_calendar_id()
        return {
            'type': 'ir.actions.act_url',
            'url': self.url,
            'target': 'new',
        }

    def _archive_future_versions(self, version=None):
        """
        Archive all versions that come after the provided version.
        If no version is provided, fallback to archiving from the contract_start_date.
        """
        self.ensure_one()
        if not self.employee_id:
            return

        # To ensure at least one version remains active
        version_to_keep = version or self.employee_version_id
        if version:
            cutoff_date = version.date_version
        else:
            cutoff_date = self.contract_start_date or fields.Date.context_today(self).replace(day=1)
        future_versions = self.employee_id.version_ids.filtered(
            lambda v: v != version_to_keep and v.date_version >= cutoff_date
        )
        if future_versions:
            future_versions.write({'active': False})
            future_versions.flush_recordset(['active'])

    def _get_simulation_required_fields(self):
        return ["salary_amount", "employee_id"]

    def check_simulation_required_fields(self):
        self.ensure_one()
        if not self.is_simulation_offer:
            return

        required_fields = self._get_simulation_required_fields()
        missing_fields = [
            self._fields[field_name].string
            for field_name in required_fields
            if not self[field_name]
        ]
        if missing_fields:
            raise UserError(self.env._("Missing required fields: %s", ", ".join(missing_fields)))
