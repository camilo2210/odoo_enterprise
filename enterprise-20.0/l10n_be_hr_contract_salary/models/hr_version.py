from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.fields import Domain
from odoo.tools.float_utils import float_round


class HrVersion(models.Model):
    _inherit = 'hr.version'

    image_1920_filename = fields.Char(tracking=1)
    id_card_filename = fields.Char(groups="hr.group_hr_user", tracking=1)
    id_card = fields.Binary(related='employee_id.id_card', groups="hr.group_hr_manager", readonly=False)
    driving_license_filename = fields.Char(groups="hr.group_hr_user", tracking=1)
    driving_license = fields.Binary(related='employee_id.driving_license', groups="hr.group_hr_manager", readonly=False)
    mobile_invoice_filename = fields.Char(groups="hr.group_hr_user", tracking=1)
    mobile_invoice = fields.Binary(related='employee_id.mobile_invoice', groups="hr.group_hr_manager", readonly=False)
    sim_card_filename = fields.Char(groups="hr.group_hr_user", tracking=1)
    sim_card = fields.Binary(related='employee_id.sim_card', groups="hr.group_hr_manager", readonly=False)
    internet_invoice_filename = fields.Char(groups="hr.group_hr_user", tracking=1)
    internet_invoice = fields.Binary(related="employee_id.internet_invoice", groups="hr.group_hr_manager", readonly=False)
    double_holiday_wage = fields.Monetary(compute='_compute_double_holiday_wage', groups="hr_payroll.group_hr_payroll_user")
    employee_type_id = fields.Many2one('hr.employee.type', "Employee Type",
                                       index='btree_not_null',
                                       default=lambda self: self.env.ref('hr.contract_type_employee',
                                                                         raise_if_not_found=False) if self.env.company.country_id.code == "BE" else self.env['hr.employee.type'])
    l10n_be_bicyle_cost = fields.Float(compute='_compute_l10n_be_bicyle_cost', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_13th_month_in_warrant = fields.Boolean("13th Month paid in warrant", groups="hr_payroll.group_hr_payroll_user")

    @api.depends('has_bicycle')
    def _compute_l10n_be_bicyle_cost(self):
        for version in self:
            if not version.has_bicycle:
                version.l10n_be_bicyle_cost = 0
            else:
                version.l10n_be_bicyle_cost = self._get_private_bicycle_cost(version.employee_id.km_home_work)

    def _get_meal_voucher_info_depends_fields(self):
        return super()._get_meal_voucher_info_depends_fields() + ['holidays']

    def _get_monthly_nb_meal_voucher(self, holidays=None):
        self.ensure_one()
        holidays = holidays if holidays is not None else self.holidays  # 0 needs to be a valid value
        return (220.0 - holidays) / 12

    @api.model
    def _get_sacrifice_fields(self):
        return super()._get_sacrifice_fields() + ['l10n_be_mobility_budget', 'l10n_be_mobility_budget_amount']

    def _get_mobility_budget_amount(self, inverse=True):
        """ Get the mobility budget based on the target yearly cost using fixed-point iteration.

        We find wage W and mobility budget MB such that:
        - yearly_cost = (W * salary_factor + benefits + MB + fixed) / ratio
        - MB = min(max_budget, W * 13 / 5)
        - W >= minimum_wage

        Where ratio accounts for holidays (sacrifice ratio).
        This ensures the mobility budget is correctly based on the final wage that achieves the target yearly cost.
        """
        if not inverse:
            return super()._get_mobility_budget_amount(inverse=inverse)

        self.ensure_one()
        today = fields.Date.context_today(self)

        mobility_budget_max = self.env['hr.rule.parameter']._get_parameter_from_code(
            "mobility_budget_max", today, raise_if_not_found=False) or 16875

        mobility_budget_min = self.env['hr.rule.parameter']._get_parameter_from_code(
            "mobility_budget_min", today, raise_if_not_found=False) or 3164

        minimum_wage = self.env['hr.rule.parameter']._get_parameter_from_code(
            'cp200_min_gross_wage', today, raise_if_not_found=False) or 2238

        minimum_wage = float_round(minimum_wage * self.work_time_rate, precision_digits=2)

        current_yearly_cost = self.env.context.get(
            'salary_simulation_full_time_yearly_cost',
            self.final_yearly_costs
        )
        # do fixed-point iteration to find consistent wage and mobility budget

        # we start with initial guess: wage without mobility budget
        wage = self._get_simulated_wage_from_yearly_costs(current_yearly_cost, mobility_budget=0)

        if not self.l10n_be_mobility_budget:
            return wage, 0.0

        mobility_budget = 0.0
        max_iterations = 20
        tolerance = 0.01  # convergence tolerance in euros

        for iteration in range(max_iterations):
            raw_mobility_budget = min(mobility_budget_max, self._get_mobility_budget_cost(wage))

            new_wage = self._get_simulated_wage_from_yearly_costs(current_yearly_cost, mobility_budget=raw_mobility_budget)

            if new_wage < minimum_wage and minimum_wage:
                mb_low = 0.0
                mb_high = raw_mobility_budget

                while mb_high - mb_low > tolerance:
                    mb_mid = (mb_low + mb_high) / 2.0
                    test_wage = self._get_simulated_wage_from_yearly_costs(current_yearly_cost, mobility_budget=mb_mid)

                    if test_wage < minimum_wage:
                        mb_high = mb_mid
                    else:
                        mb_low = mb_mid

                mobility_budget = mb_low
                break

            if abs(new_wage - wage) < tolerance and abs(raw_mobility_budget - mobility_budget) < tolerance:
                mobility_budget = raw_mobility_budget
                break

            wage = new_wage
            mobility_budget = raw_mobility_budget

        # We have to ensure that we respect the minimum mobility budget, and if this is higher than
        # the optimal one, we have to recompute the corresponding wage
        final_mobility_budget = max(float_round(mobility_budget, precision_digits=2), mobility_budget_min)
        final_wage = self._get_simulated_wage_from_yearly_costs(current_yearly_cost, mobility_budget=final_mobility_budget)

        return final_wage, final_mobility_budget

    def _get_mobility_budget_cost_ratio(self):
        """ 12 months
            + 13e month (except if paid in warrants)
            - simple holiday allowance (20 days/4 weeks ≃ 0.92 month) """
        self.ensure_one()
        ratio = super()._get_mobility_budget_cost_ratio()
        return ratio - 1 if self.l10n_be_13th_month_in_warrant else ratio

    def _inverse_final_yearly_costs(self):
        is_simulation = self.env.context.get('salary_simulation')
        belgian_versions = self.filtered(lambda v: v.company_id.country_id.code == 'BE')
        non_belgium_versions = self - belgian_versions
        if non_belgium_versions:
            super(HrVersion, non_belgium_versions)._inverse_final_yearly_costs()
        if belgian_versions:
            if not is_simulation:
                super(HrVersion, belgian_versions)._inverse_final_yearly_costs()
            else:
                for version in belgian_versions:
                    if version.l10n_be_mobility_budget:
                        wage, mobility_budget = version._get_mobility_budget_amount()
                        version.wage = wage
                        version.l10n_be_mobility_budget_amount = mobility_budget
                    else:
                        version.wage = version._get_wage_from_yearly_costs(version.final_yearly_costs)
                        version.l10n_be_mobility_budget_amount = 0

    def _get_simulated_wage_from_yearly_costs(self, yearly_cost, ratio=None, fixed=None, mobility_budget=0):
        self.ensure_one()
        ratio = ratio or self._get_yearly_cost_sacrifice_ratio()
        fixed = fixed or self._get_yearly_cost_sacrifice_fixed()
        if self.l10n_be_mobility_budget and self.l10n_be_mobility_budget_amount:
            fixed = fixed - self.l10n_be_mobility_budget_amount
        salary_costs_factor = self._get_salary_costs_factor()
        if salary_costs_factor:
            return (yearly_cost - fixed - self._get_benefits_costs() - mobility_budget) * ratio / salary_costs_factor
        return 0

    @api.model
    def _get_private_bicycle_cost(self, distance):
        amount_per_km = self.env['hr.rule.parameter'].sudo()._get_parameter_from_code('cp200_cycle_reimbursement_per_km', raise_if_not_found=False) or 0.20
        amount_max = self.env['hr.rule.parameter'].sudo()._get_parameter_from_code('cp200_cycle_reimbursement_max', raise_if_not_found=False) or 8
        return 4 * min(amount_max, amount_per_km * distance * 2)

    @api.depends('wage')
    def _compute_double_holiday_wage(self):
        for version in self:
            version.double_holiday_wage = version.wage * 0.92

    @api.model
    def _benefit_white_list(self):
        return super()._benefit_white_list() + [
            'yearly_commission_cost',
            'meal_voucher_average_monthly_amount',
            'l10n_be_bicyle_cost',
            'double_holiday_wage',
        ]

    def _get_benefit_values_company_car_total_depreciated_cost(self, version_vals, benefits):
        has_car = benefits['fold_company_car_total_depreciated_cost']
        selected_car = benefits.get('select_company_car_total_depreciated_cost')
        if not has_car or not selected_car:
            return {
                'transport_mode_car': False,
                'has_new_car': False,
                'new_car_model_id': False,
                'car_id': False,
            }
        car, car_id = selected_car.split('-')
        new_car = car == 'new'
        if new_car:
            return {
                'transport_mode_car': True,
                'has_new_car': True,
                'new_car_model_id': int(car_id),
                'car_id': False,
            }
        return {
            'transport_mode_car': True,
            'has_new_car': False,
            'new_car_model_id': False,
            'car_id': int(car_id),
        }

    def _get_benefit_values_company_bike_depreciated_cost(self, version_vals, benefits):
        has_bike = benefits['fold_company_bike_depreciated_cost']
        selected_bike = benefits.get('select_company_bike_depreciated_cost', None)
        if not has_bike or not selected_bike:
            return {
                'transport_mode_bike': False,
                'new_bike_model_id': False,
                'bike_id': False,
            }
        bike, bike_id = selected_bike.split('-')
        new_bike = bike == 'new'
        if new_bike:
            return {
                'transport_mode_bike': False,
                'new_bike': True,
                'new_bike_model_id': int(bike_id),
                'bike_id': False,
            }
        return {
            'transport_mode_bike': True,
            'new_bike': False,
            'new_bike_model_id': False,
            'bike_id': int(bike_id),
        }

    def _get_benefit_values_temporary_car_total_depreciated_cost(self, version_vals, benefits):
        if benefits.get('fold_temporary_car_total_depreciated_cost', False):
            car_options = benefits.get('select_temporary_car_total_depreciated_cost', '')
            car_id = car_options.split('-')[1] if '-' in car_options else None
            new_car_model = benefits.get('select_company_car_total_depreciated_cost', '')
            new_car_model_id = new_car_model.split('-')[1] if new_car_model and new_car_model.startswith('new-') else False

            return {
                'has_new_car': True,
                'car_id': int(car_id) if car_id else False,
                'new_car_model_id': int(new_car_model_id) if new_car_model_id else False,
                'transport_mode_car': True,
            }
        else:
            return {}

    def _get_benefit_values_insured_relative_spouse(self, version_vals, benefits):
        return {'insured_relative_spouse': benefits['fold_insured_relative_spouse']}

    def _get_benefit_values_l10n_be_ambulatory_insured_spouse(self, version_vals, benefits):
        return {'l10n_be_ambulatory_insured_spouse': benefits['fold_l10n_be_ambulatory_insured_spouse']}

    def _get_description_company_car_total_depreciated_cost(self, new_value=None):
        benefit = self.env.ref('l10n_be_hr_payroll.l10n_be_transport_company_car')
        description = benefit.description or ""
        if not new_value:
            if self.car_id:
                new_value = 'old-%s' % self.car_id.id
            elif self.new_car_model_id:
                new_value = 'new-%s' % self.new_car_model_id.id
            else:
                return description
        car_option, vehicle_id = new_value.split('-')
        try:
            vehicle_id = int(vehicle_id)
        except ValueError:
            return description
        if car_option == "new":
            vehicle = self.env['fleet.vehicle.model'].with_company(self.company_id).sudo().browse(vehicle_id)
        else:
            vehicle = self.env['fleet.vehicle'].with_company(self.company_id).sudo().browse(vehicle_id)

        is_new = bool(car_option == "new")

        car_elements = self._get_company_car_description_values(vehicle, is_new)
        description += Markup('<div class="d-flex row">%s</div>') % Markup().join([
        Markup('<div class="col"><span class="vehicle_elements_label">%s</span><b class="vehicle_description_value">%s</b></div>') % (key, value)
        for key, value in car_elements.items() if value])
        if car_option == "old" and vehicle.description:
            description += Markup('<div class="car_description_value">%s</div>') % vehicle.description
        return description

    def _get_description_temporary_car_total_depreciated_cost(self, new_value=None):
        benefit = self.env.ref('l10n_be_hr_payroll.l10n_be_transport_temporary_car')
        description = benefit.description or ""
        if not new_value:
            return description
        vehicle_id = new_value.split('-')[1]
        try:
            vehicle_id = int(vehicle_id)
        except ValueError:
            return description

        vehicle = self.env['fleet.vehicle'].with_company(self.company_id).sudo().browse(vehicle_id)
        car_elements = self._get_company_car_description_values(vehicle, False)
        description += Markup('<div class="d-flex row">%s</div>') % Markup().join([
        Markup('<div class="col"><span class="vehicle_elements_label">%s</span><b class="vehicle_description_value">%s</b></div>') % (key, value)
        for key, value in car_elements.items() if value])
        if vehicle.description:
            description += Markup('<div class="car_description_value">%s</div>') % vehicle.description
        return description

    def _get_description_company_bike_depreciated_cost(self, new_value):
        benefit = self.env.ref('l10n_be_hr_payroll.l10n_be_transport_company_bike')
        description = benefit.description or ""
        if not new_value:
            if self.bike_id:
                new_value = 'old-%s' % self.bike_id.id
            else:
                return description
        bike_option, bike_id = new_value.split('-')
        if bike_option == "new":
            bike = self.env['fleet.vehicle.model'].with_company(self.company_id).sudo().browse(int(bike_id))
        else:
            bike = self.env['fleet.vehicle'].with_company(self.company_id).sudo().browse(int(bike_id))

        bike_elements = {
            'Electric Assistance': _("Yes") if bike.electric_assistance else _("No"),
            'Color': bike.color if bike_option == "old" else False,
            'Bike Frame Type': bike.frame_type if bike_option == "old" else False,
            'Frame Size (cm)': bike.frame_size if bike_option == "old" else False,
        }

        description += Markup('<div class="d-flex row">%s</div>') % Markup().join([
        Markup('<div class="col"><span class="vehicle_elements_label">%s</span><b class="vehicle_description_value">%s</b></div>') % (key, value)
        for key, value in bike_elements.items() if value])
        return description

    def _get_company_car_description_values(self, vehicle_id, is_new):
        vehicle_range = _("%(range)s %(unit)s",
            range=vehicle_id.vehicle_range, unit=vehicle_id.range_unit) if vehicle_id.vehicle_range else False
        if is_new:
            co2 = _("%(co2)s %(unit)s", co2=vehicle_id.default_co2,
                unit=vehicle_id.co2_emission_unit) if vehicle_id.default_co2 else False
            fuel_type = vehicle_id.default_fuel_type
            transmission = vehicle_id.transmission
            odometer = False
            door_number = vehicle_id.doors
            trailer_hook = False
        else:
            co2 = _("%(co2)s %(unit)s", co2=vehicle_id.co2,
                unit=vehicle_id.co2_emission_unit) if vehicle_id.co2 else False
            fuel_type = vehicle_id.fuel_type
            door_number = vehicle_id.doors
            odometer = vehicle_id.odometer
            transmission = vehicle_id.transmission
            trailer_hook = "Yes" if vehicle_id.trailer_hook else False

        car_elements = {
            'CO2 Emission': co2,
            'Fuel Type': fuel_type,
            'Range': vehicle_range,
            'Transmission': transmission,
            'Doors Number': door_number,
            'Trailer Hook': trailer_hook,
            'Odometer': odometer,
        }
        return car_elements

    def _get_description_commission_on_target(self, new_value=None):
        self.ensure_one()
        return '<span class="form-text">The commission is scalable and starts from the 1st € sold. The commission plan has stages with accelerators. At 100%%, 3 months are paid in Warrant which results to a monthly NET commission value of %s € and 9 months in cash which result in a GROSS monthly commission of %s €, taxable like your usual monthly pay.</span>' % (round(self.warrant_value_employee, 2), round(self.commission_on_target, 2))

    def _get_benefit_values_ip_value(self, version_vals, benefits):
        return {
            'ip_wage_rate': version_vals.get('ip_wage_rate')
        }

    def _get_available_cars_domain(self):
        return Domain.AND(
            [
                super()._get_available_cars_domain(),
                Domain('state_id.hide_in_offer', '=', False),
            ],
        )
