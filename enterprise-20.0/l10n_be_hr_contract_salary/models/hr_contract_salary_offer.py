from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _


class HrContractSalaryOffer(models.Model):
    _inherit = 'hr.contract.salary.offer'
    _description = 'Salary Package Offer'

    employee_type_id = fields.Many2one(
        'hr.employee.type', "Employee Type",
        compute='_compute_employee_type_id',
        store=True,
        readonly=False,
        tracking=True)
    new_car_options = fields.Selection(
        string='Company Car', tracking=True,
        selection=[
            ('all_options', "Available & New"),
            ('available', "Available"),
            ('none', "No Option"),
        ],
        default='all_options',
        required=True,
        help="It determines the vehicle options that will be available for the employee to choose from.")
    car_id = fields.Many2one(
        'fleet.vehicle', string='Default Vehicle',
        compute='_compute_car_id',
        store=True,
        readonly=False, domain="[('vehicle_type', '=', 'car')]",
        help="Default employee's company car. If left empty, the default value will be the employee's current car.")
    additional_car_ids = fields.Many2many('fleet.vehicle', domain="[('vehicle_type', '=', 'car')]", string="Additional cars",
                                          help="You can add used cars to this field, they'll be added to the list for simulation purposes.")
    assigned_car_warning = fields.Char(compute='_compute_assigned_car_warning')
    wishlist_car_warning = fields.Char(compute='_compute_wishlist_car_warning')
    l10n_be_offer_seniority = fields.Integer(string="Hiring Seniority (Years)", compute='_compute_l10n_be_offer_seniority', readonly=False, store=True)
    l10n_be_offer_seniority_months = fields.Integer(string="Hiring Seniority (Months)", compute='_compute_l10n_be_offer_seniority', readonly=False, store=True)
    l10n_be_is_below_scale_warning = fields.Char(compute='_compute_l10n_be_is_below_scale', compute_sudo=True)

    @api.depends('contract_template_id')
    def _compute_employee_type_id(self):
        for offer in self:
            offer.employee_type_id = offer.contract_template_id.employee_type_id

    @api.depends('applicant_id.partner_id', 'employee_id', 'contract_template_id')
    def _compute_car_id(self):
        for offer in self:
            contract = offer.contract_template_id
            version = offer.employee_version_id
            if contract and contract.transport_mode_car and contract.car_id:
                offer.car_id = contract.car_id
                continue
            if version and version.transport_mode_car and version.car_id:
                offer.car_id = version.car_id
                continue

            partner = self.env['res.partner']
            car = self.env['fleet.vehicle']
            if offer.employee_id:
                partner |= offer.employee_id.work_contact_id
                # In case the car was reserved for an applicant, while
                # the offer is sent for the corresponding employee
                if applicant_partner_id := offer.employee_id.sudo().applicant_ids.partner_id:
                    partner |= applicant_partner_id
            elif offer.applicant_id:
                partner |= offer.applicant_id.partner_id
            if partner:
                car_is_driver = self.env['fleet.vehicle'].search([
                    ('future_driver_id', '=', False),
                    ('driver_id', 'in', partner.ids),
                    ('vehicle_type', '=', 'car'),
                ], limit=1)
                car_is_future_driver = self.env['fleet.vehicle'].search([
                    ('future_driver_id', 'in', partner.ids),
                    ('driver_id', '=', False),
                    ('vehicle_type', '=', 'car'),
                ], limit=1)
                car = car_is_driver or car_is_future_driver
            offer.car_id = car

    @api.depends('applicant_id.partner_id', 'employee_id', 'car_id')
    def _compute_assigned_car_warning(self):
        self.assigned_car_warning = False
        for offer in self:
            warning = []
            partners = self.env['res.partner']
            if offer.applicant_id:
                partners |= offer.applicant_id.partner_id
            elif offer.employee_id:
                partners |= offer.employee_id.work_contact_id
                if applicant_partner_id := offer.employee_id.sudo().applicant_ids.partner_id:
                    partners |= applicant_partner_id
            if offer.car_id.driver_id and offer.car_id.driver_id not in partners:
                warning.append(f"Car is already assigned to {offer.car_id.driver_id.name} as a driver.")
            if offer.car_id.future_driver_id and offer.car_id.future_driver_id not in partners:
                warning.append(f"Car is already assigned to {offer.car_id.future_driver_id.name} as a future driver.")
            if warning:
                offer.assigned_car_warning = f"Warning: {' '.join(warning)}"

    @api.depends('new_car_options')
    def _compute_wishlist_car_warning(self):
        for offer in self:
            if offer.contract_template_id.available_cars_amount >= offer.company_id.l10n_be_max_unused_cars:
                offer.wishlist_car_warning = _("We already have %s car(s) without driver(s) available",
                                              offer.employee_version_id.available_cars_amount)
            else:
                offer.wishlist_car_warning = False

    @api.depends('employee_id')
    def _compute_l10n_be_offer_seniority(self):
        for offer in self:
            offer.l10n_be_offer_seniority = offer.employee_id.l10n_be_scale_seniority
            offer.l10n_be_offer_seniority_months = offer.employee_id.l10n_be_scale_seniority_months

    def _get_below_scale_warning_excluded_offers(self):
        return self.filtered(
            lambda o: o.employee_version_id.l10n_be_joint_committee_id.egov3_code == '999' or
                (o.employee_version_id.l10n_be_egov3_code == '200' and o.employee_version_id.l10n_be_is_sale_representative)
        )

    @api.depends(
        'gross_wage', 'employee_version_id.l10n_be_salary_scale_id', 'l10n_be_offer_seniority', 'l10n_be_offer_seniority_months',
        'employee_id.work_time_rate', 'employee_id.l10n_be_time_credit', 'employee_version_id.l10n_be_dimona_category',
        'employee_version_id.l10n_be_joint_committee_id')
    def _compute_l10n_be_is_below_scale(self):
        # Source: https://salairesminimums.be/index.html
        today = fields.Date.context_today(self)
        excluded_offers = self._get_below_scale_warning_excluded_offers()
        excluded_offers.l10n_be_is_below_scale_warning = False
        applicable_offers = self - excluded_offers
        for structure_type, offers_per_structure_type in applicable_offers.grouped('structure_type_id').items():
            if structure_type == self.env.ref('hr.structure_type_employee_cp200'):
                for offer in offers_per_structure_type:
                    target = offer.employee_id
                    if not offer.employee_version_id or not offer.employee_version_id.l10n_be_salary_scale_id:
                        offer.l10n_be_is_below_scale_warning = False
                        continue
                    if offer.employee_version_id.l10n_be_dimona_category == 'stu':
                        age = target._get_age()
                        min_wage = offer.employee_version_id._get_student_min_wage(
                            offer.employee_version_id.l10n_be_salary_scale_id.code,
                            age,
                            offer.employee_version_id.wage_type,
                            offer.employee_version_id.resource_calendar_id.hours_per_week,
                        )
                    else:
                        company_seniority = 0
                        if target:
                            company_seniority = relativedelta(today, target._get_first_contract_date())
                        seniority = company_seniority.years + offer.l10n_be_offer_seniority + (offer.l10n_be_offer_seniority_months + company_seniority.months) // 12
                        min_wage = offer.employee_version_id._get_employee_min_wage(
                            salary_scale=offer.employee_version_id.l10n_be_salary_scale_id.code,
                            company_seniority=company_seniority.years,
                            seniority=seniority,
                            wage_type=offer.employee_version_id.wage_type,
                            hours_per_week=offer.employee_version_id.resource_calendar_id.hours_per_week,
                        )
                    if min_wage == 0:
                        offer.l10n_be_is_below_scale_warning = False
                        continue
                    if target:
                        min_wage = min_wage * target.work_time_rate
                    if offer.gross_wage < min_wage:
                        scale_type = "age" if offer.employee_version_id.l10n_be_dimona_category == 'stu' else "seniority"
                        scale_value = age if offer.employee_version_id.l10n_be_dimona_category == 'stu' else seniority
                        offer.l10n_be_is_below_scale_warning = offer.employee_version_id._get_min_wage_warning_message(scale_type, scale_value, min_wage, offer._fields["gross_wage"].string)
                    else:
                        offer.l10n_be_is_below_scale_warning = False
            else:
                offers_per_structure_type.l10n_be_is_below_scale_warning = False

    def _get_simulation_required_fields(self):
        res = super()._get_simulation_required_fields()
        if self.country_code == 'BE':
            res.append("employee_job_id")
        return res
