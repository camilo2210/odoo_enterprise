# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    dmfa_location_unit_ids = fields.One2many('hr.work.location', 'company_id', string="Establishment unit codes")
    onss_expeditor_number = fields.Char(
        string="ONSS Client ID", groups="hr_payroll.group_hr_payroll_user",
        help="ONSS Expeditor Number provided when registering service on the technical user. Eg: self_service_chaman_123456_98jdnvh63y")
    onss_certificate_id = fields.Many2one(
        string="ONSS Certificate",
        comodel_name="certificate.certificate",
        domain=[('is_valid', '=', True)],
        help="Certificate to allow access to batch declarations")
    onss_technical_user_name = fields.Char(string="ONSS Technical User Name", groups="base.group_system",
        help="ONSS Technical User Name provided when registering service on the ONSS platform")
    onss_sftp_private_key = fields.Many2one('certificate.key', string="ONSS Technical User Private Key", groups="base.group_system")
    nsso_immatriculation_date = fields.Date(string="NSSO Immatriculation Date", groups="hr_payroll.group_hr_payroll_user")
    l10n_be_dimona_environment = fields.Selection([
        ('production', 'Production'),
        ('test', 'Test'),
        ('sandbox', 'Sandbox'),
    ], string="Dimona Environment", default='production', required=True)
    l10n_be_joint_committee_id = fields.Many2one('l10n.be.joint.committee', string="Joint Committee")
    l10n_be_cash_register_active = fields.Boolean(string="Cash Register Active")
    l10n_be_cash_register_number = fields.Char(string="Cash Register Number")
    l10n_be_cash_register_registration_start = fields.Date(string="Cash Register Registration Start")
    l10n_be_cash_register_registration_end = fields.Date(string="Cash Register Registration End")
    l10n_be_daily_registration_recording = fields.Selection([
        ('1', '1 - Only use daily registration system'),
        ('2', '2 - Use cash register system'),
        ('3', '3 - Use both systems'),
    ], string="Daily Registration Recording")
    l10n_be_has_employees = fields.Boolean(string="Has Non-Director Employees", compute='_compute_l10n_be_has_employees')
    l10n_be_has_workers = fields.Boolean(compute='_compute_l10n_be_has_workers')
    l10n_be_employer_category_has_cp302 = fields.Boolean(
        string="Employer Category Allows CP302",
        compute='_compute_l10n_be_employer_category_has_cp302')
    l10n_be_cbe_inscription = fields.Date(string="CBE Inscription")
    l10n_be_temporary_car_option = fields.Boolean(string='Temporary Car Option')
    l10n_be_max_unused_cars = fields.Integer(string='Maximum unused cars')
    l10n_be_has_white_cash_register = fields.Boolean(
        string="White Cash Register",
        help="If checked, the company has a white cash register, which impacts the extra hours cap for CP302 employees in the 274.XX withholding tax exemption. The cap is raised from 300h to 360h.")

    def _compute_l10n_be_has_employees(self):
        director_jc_id = self.env['l10n.be.joint.committee'].search([('egov3_code', '=', '999')], limit=1).id
        for company in self:
            origin_id = company._origin.id
            if not origin_id:
                company.l10n_be_has_employees = False
                continue
            company.l10n_be_has_employees = bool(
                self.env["hr.employee"].search(
                    [("company_id", "=", origin_id), ("l10n_be_joint_committee_id", "!=", director_jc_id)],
                    limit=1,
                ),
            )

    def _compute_l10n_be_has_workers(self):
        origin_companies = self._origin.filtered('id')
        employees_by_company = (
            self.env["hr.employee"]
            .search([("company_id", "in", origin_companies.ids)])
            .grouped('company_id')
        ) if origin_companies else {}

        for company in self:
            origin = company._origin
            if not origin.id:
                company.l10n_be_has_workers = False
                continue
            employees = employees_by_company.get(origin, [])
            company.l10n_be_has_workers = any(
               e.version_id and e.version_id.is_worker() for e in employees
            )

    @api.depends('payroll_config_ids.l10n_be_employer_category_id.allowed_joint_committee_ids')
    def _compute_l10n_be_employer_category_has_cp302(self):
        cp302 = self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_302', raise_if_not_found=False)
        for company in self:
            category = company.current_payroll_config_id.l10n_be_employer_category_id
            company.l10n_be_employer_category_has_cp302 = bool(
                cp302 and cp302 in category.allowed_joint_committee_ids
            )

    def _l10n_be_dimona_can_declare(self, payroll_config=None):
        """Whether Dimona declarations can be filed for this company."""
        self.ensure_one()
        if self.l10n_be_dimona_environment == 'sandbox':
            return True
        config = self.current_payroll_config_id if payroll_config is None else payroll_config
        return bool(config.onss_registration_number and self.onss_certificate_id)

    def _l10n_be_dimona_uses_rest_api(self):
        """Whether this company talks to the ONSS Dimona REST API itself.

        A database that does not file over REST must not poll over REST either.
        """
        self.ensure_one()
        return self.l10n_be_dimona_environment in ('production', 'test', 'sandbox')

    def _prepare_resource_calendar_values(self):
        """
        Override to set the default calendar to
        38 hours/week for Belgian companies
        """
        vals = super()._prepare_resource_calendar_values()
        if self.country_id.code == 'BE':
            vals.update({
                'name': self.env._('38 hours/week'),
                'hours_per_day': 7.6,
                'full_time_required_hours': 38.0,
                'attendance_ids': [
                    (0, 0, {'dayofweek': '0', 'duration_hours': 7.6, 'hour_from': 0, 'hour_to': 0}),
                    (0, 0, {'dayofweek': '1', 'duration_hours': 7.6, 'hour_from': 0, 'hour_to': 0}),
                    (0, 0, {'dayofweek': '2', 'duration_hours': 7.6, 'hour_from': 0, 'hour_to': 0}),
                    (0, 0, {'dayofweek': '3', 'duration_hours': 7.6, 'hour_from': 0, 'hour_to': 0}),
                    (0, 0, {'dayofweek': '4', 'duration_hours': 7.6, 'hour_from': 0, 'hour_to': 0}),
                ],
            })
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            if company.country_id.code == 'BE':
                self.env['hr.work.location'].sudo().create({
                    "name": f"{company.name} - {self.env._('Work Location')}",
                    "company_id": company.id,
                    "address_id": company.partner_id.id,
                    "location_type": "dmfa_unit",
                })
        return companies
