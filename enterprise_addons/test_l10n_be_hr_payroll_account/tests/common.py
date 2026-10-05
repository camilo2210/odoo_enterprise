# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time
from datetime import date

import odoo.tests
from odoo.addons.l10n_be_hr_payroll.tests.common import TestBelgiumCommon
from odoo.addons.mail.tests.common import mail_new_test_user


class TestPayrollAccountCommon(odoo.tests.HttpCase, TestBelgiumCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # no user available for belgian company so to set hr responsible change company of demo
        demo = mail_new_test_user(
            cls.env,
            email='be_demo@test.example.com',
            groups='hr.group_hr_user,sign.group_sign_user',
            login='be_demo',
            name="Laurie Poiret",
        )
        cls.pdf_content = cls.file_read('hr_contract_salary/static/src/demo/employee_contract.pdf')

        attachment = cls.env['ir.attachment'].create({
            'type': 'binary',
            'raw': cls.pdf_content,
            'name': 'test_employee_contract.pdf',
        })

        cls.template = cls.env['sign.template'].create({})

        cls.document_id = cls.env['sign.document'].create({
            'attachment_id': attachment.id,
            'template_id': cls.template.id,
        })

        version_model = cls.env['ir.model']._get('hr.version')
        type_employee_name, type_city, type_country_name, type_street, type_children = cls.env['sign.item.type'].create([
            {
                'name': 'Employee Name',
                'placeholder': 'legal_name',
                'item_type': 'text',
                'model_id': version_model.id,
                'auto_field': 'employee_id.legal_name',
             },
            {
                'name': 'Private City',
                'placeholder': 'City',
                'item_type': 'text',
                'model_id': version_model.id,
                'auto_field': 'private_city',
            },
            {
                'name': 'Country',
                'placeholder': 'Country',
                'item_type': 'text',
                'model_id': version_model.id,
                'auto_field': 'private_country_id.name',
            },
            {
                'name': 'Street',
                'placeholder': 'Street',
                'item_type': 'text',
                'model_id': version_model.id,
                'auto_field': 'private_street',
            }, {
                'name': 'Children',
                'placeholder': 'Children',
                'item_type': 'text',
                'model_id': version_model.id,
                'auto_field': 'children',
            }
        ])
        cls.env['sign.item'].create([
            {
                'type_id': type_employee_name.id,
                'name': 'Name',
                'required': True,
                'constant': True,
                'responsible_id': cls.env.ref('hr_sign.sign_item_role_employee_signatory').id,
                'page': 1,
                'posX': 0.273,
                'posY': 0.158,
                'document_id': cls.document_id.id,
                'width': 0.150,
                'height': 0.015,
            }, {
                'type_id': cls.env.ref('sign.sign_item_type_date').id,
                'name': False,
                'required': True,
                'responsible_id': cls.env.ref('hr_sign.sign_item_role_employee_signatory').id,
                'page': 1,
                'posX': 0.707,
                'posY': 0.158,
                'document_id': cls.document_id.id,
                'width': 0.150,
                'height': 0.015,
            }, {
                'type_id': type_city.id,
                'name': 'City',
                'required': True,
                'constant': True,
                'responsible_id': cls.env.ref('hr_sign.sign_item_role_employee_signatory').id,
                'page': 1,
                'posX': 0.506,
                'posY': 0.184,
                'document_id': cls.document_id.id,
                'width': 0.150,
                'height': 0.015,
            }, {
                'type_id': type_country_name.id,
                'name': 'Country',
                'required': True,
                'constant': True,
                'responsible_id': cls.env.ref('hr_sign.sign_item_role_employee_signatory').id,
                'page': 1,
                'posX': 0.663,
                'posY': 0.184,
                'document_id': cls.document_id.id,
                'width': 0.150,
                'height': 0.015,
            }, {
                'type_id': type_street.id,
                'name': 'Street',
                'required': True,
                'constant': True,
                'responsible_id': cls.env.ref('hr_sign.sign_item_role_employee_signatory').id,
                'page': 1,
                'posX': 0.349,
                'posY': 0.184,
                'document_id': cls.document_id.id,
                'width': 0.150,
                'height': 0.015,
            }, {
                'type_id': cls.env.ref('sign.sign_item_type_signature').id,
                'name': False,
                'required': True,
                'responsible_id': cls.env.ref('hr_sign.sign_item_role_job_responsible').id,
                'page': 2,
                'posX': 0.333,
                'posY': 0.575,
                'document_id': cls.document_id.id,
                'width': 0.200,
                'height': 0.050,
            }, {
                'type_id': cls.env.ref('sign.sign_item_type_signature').id,
                'name': False,
                'required': True,
                'responsible_id': cls.env.ref('hr_sign.sign_item_role_employee_signatory').id,
                'page': 2,
                'posX': 0.333,
                'posY': 0.665,
                'document_id': cls.document_id.id,
                'width': 0.200,
                'height': 0.050,
            }, {
                'type_id': cls.env.ref('sign.sign_item_type_date').id,
                'name': False,
                'required': True,
                'responsible_id': cls.env.ref('hr_sign.sign_item_role_employee_signatory').id,
                'page': 2,
                'posX': 0.665,
                'posY': 0.694,
                'document_id': cls.document_id.id,
                'width': 0.150,
                'height': 0.015,
            }, {
                'type_id': type_children.id,
                'constant': True,
                'name': 'Children',
                'required': True,
                'responsible_id': cls.env.ref('hr_sign.sign_item_role_employee_signatory').id,
                'page': 2,
                'posX': 0.665,
                'posY': 0.694,
                'document_id': cls.document_id.id,
                'width': 0.150,
                'height': 0.015,
             }
        ])

        cls.extra_days_time_off_type = cls.env['hr.work.entry.type'].create({
            'name': 'Extra Time Off',
            'code': 'Extra Time Off',
            'requires_allocation': 'yes',
            'country_id': cls.env.ref('base.be').id,
        })

        cls.company_id = cls.env['res.company'].create({
            'name': 'My Belgian Company - TEST',
            'country_id': cls.env.ref('base.be').id,
        })
        cls.company_id.resource_calendar_id.reference_calendar_id = cls.company_id.resource_calendar_id
        cls.company_id.current_payroll_config_id.write({
            'l10n_be_employer_category_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_employer_category_00010').id,
            'hospital_insurance_amount_child': 7.2,
            'hospital_insurance_amount_adult': 20.5,
        })

        cls.cp200 = cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200')

        ir_default = cls.env['ir.default'].sudo()
        ir_default.set('hr.version', 'meal_voucher_amount', 7.45, company_id=cls.company_id.id)
        ir_default.set('hr.version', 'internet', 38.0, company_id=cls.company_id.id)
        ir_default.set('hr.version', 'mobile', 30.0, company_id=cls.company_id.id)
        ir_default.set('hr.version', 'fuel_card', 150.0, company_id=cls.company_id.id)
        partner_id = cls.env['res.partner'].create({
            'name': 'Laurie Poiret',
            'street': '58 rue des Wallons',
            'city': 'Louvain-la-Neuve',
            'zip': '1348',
            'country_id': cls.env.ref("base.be").id,
            'phone': '+0032476543210',
            'email': 'laurie.poiret@example.com',
            'company_id': cls.company_id.id,
        })

        bike_brand = cls.env['fleet.vehicle.model.brand'].create({
            'name': 'Bike Brand',
        })

        cls.env['fleet.vehicle.model'].with_company(cls.company_id).create({
            'name': 'Bike 1',
            'brand_id': bike_brand.id,
            'vehicle_type': 'bike',
            'can_be_requested': True,
            'default_car_value': 1000,
            'default_recurring_cost_amount_depreciated': 25,
        })

        cls.env['fleet.vehicle.model'].with_company(cls.company_id).create({
            'name': 'Bike 2',
            'brand_id': bike_brand.id,
            'vehicle_type': 'bike',
            'can_be_requested': True,
            'default_car_value': 2000,
            'default_recurring_cost_amount_depreciated': 50,
        })
        cls.model_a3 = cls.env["fleet.vehicle.model"].with_company(cls.company_id).create({
            'name': ' A3',
            'brand_id': cls.env.ref('fleet.brand_audi').id,
            'default_recurring_cost_amount_depreciated': 450,
            'can_be_requested': True,
            'vehicle_type': 'car',
        })

        cls.model_category_compact = cls.env["fleet.vehicle.model.category"].create({'name': 'Compact Test'})

        cls.model_corsa = cls.env["fleet.vehicle.model"].with_company(cls.company_id).create({
            'name': 'Corsa',
            'vehicle_type': 'car',
            'brand_id': cls.env.ref('fleet.brand_opel').id,
            'category_id': cls.model_category_compact.id,
            'default_car_value': 18000,
            'default_co2': 88,
            'default_fuel_type': 'diesel',
            'default_recurring_cost_amount_depreciated': '450.00',
            'can_be_requested': True,
        })

        vehicle = cls.env['fleet.vehicle'].create({
            'model_id': cls.model_a3.id,
            'license_plate': '1-JFC-094',
            'acquisition_date': time.strftime('%Y-01-01'),
            'co2': 88,
            'plan_to_change_vehicle': True,
            'car_value': 38000,
            'company_id': cls.company_id.id,
        })
        cls.env['fleet.vehicle.log.contract'].create({
            'vehicle_id': vehicle.id,
            'recurring_cost_amount_depreciated': vehicle.model_id.default_recurring_cost_amount_depreciated,
            'purchaser_id': vehicle.driver_id.id,
            'company_id': vehicle.company_id.id,
            'user_id': vehicle.manager_id.id if vehicle.manager_id else cls.env.user.id,
            'start_date': date.today(),
        })

        if not cls.env.ref('fleet.fleet_vehicle_state_waiting_list', raise_if_not_found=False):
            waiting_list_state = cls.env['fleet.vehicle.state'].create({
                'name': 'Waiting List',
                'sequence': 10,
            })
            cls.env['ir.model.data'].create({
                'name': 'fleet_vehicle_state_waiting_list',
                'module': 'fleet',
                'model': 'fleet.vehicle.state',
                'res_id': waiting_list_state.id,
            })

        a_recv = cls.env['account.account'].create({
            'code': 'X1012',
            'name': 'Debtors - (test)',
            'account_type': 'asset_receivable',
            'company_ids': cls.company_id.ids,
        })
        a_pay = cls.env['account.account'].create({
            'code': 'X1111',
            'name': 'Creditors - (test)',
            'account_type': 'liability_payable',
            'company_ids': cls.company_id.ids,
        })
        cls.env['ir.default'].set(
            'res.partner',
            'property_account_receivable_id',
            a_recv.id,
            company_id=cls.company_id.id,
        )
        cls.env['ir.default'].set(
            'res.partner',
            'property_account_payable_id',
            a_pay.id,
            company_id=cls.company_id.id,
        )

        cls.env.ref('base.user_admin').write({
            'company_ids': [(4, cls.company_id.id)],
            'name': 'Mitchell Admin',
            'sign_signature': cls.file_read('sign/static/demo/signature.png'),
        })
        cls.env.ref('base.user_admin').partner_id.write({
            'email': 'mitchell.stephen@example.com',
            'name': 'Mitchell Admin',
            'street': '215 Vine St',
            'city': 'Scranton',
            'zip': '18503',
            'country_id': cls.env.ref('base.us').id,
            'state_id': cls.env.ref('base.state_us_39').id,
            'phone': '+1 555-555-5555',
            'tz': 'Europe/Brussels',
            'company_id': cls.env.company.id,
        })
        demo.write({
            'partner_id': partner_id,
            'company_id': cls.company_id.id,
            'company_ids': [(4, cls.company_id.id)]
        })
        cls.env.ref('base.main_partner').email = "info@yourcompany.example.com"

        cls.new_dev_contract = cls.env['hr.version'].with_company(cls.company_id).create({
            'hospital_insurance_amount_per_child': 7.2,
            'hospital_insurance_amount_per_adult': 20.5,
            'name': 'New Developer Template Contract',
            'wage': 3000,
            'structure_type_id': cls.env.ref('hr.structure_type_employee_cp200').id,
            'ip_wage_rate': 0.25,
            'sign_template_id': cls.template.id,
            'contract_update_template_id': cls.template.id,
            'hr_responsible_id': cls.env.ref('base.user_admin').id,
            'company_id': cls.company_id.id,
            'meal_voucher_amount': 7.45,
            'fuel_card': 0,
            'internet': 38,
            'mobile': 30,
            'car_id': False,
            'l10n_be_lsa_monthly_pro_other_amount': 150,
            'l10n_be_joint_committee_id': cls.cp200.id,
            'laptop': 100,
            'rd_percentage': 0.75,
        })

        cls.senior_dev_contract = cls.env['hr.version'].with_company(cls.company_id).create({
            'hospital_insurance_amount_per_child': 7.2,
            'hospital_insurance_amount_per_adult': 20.5,
            'name': 'Senior Developer Template Contract',
            'wage': 6000,
            'structure_type_id': cls.env.ref('hr.structure_type_employee_cp200').id,
            'ip_wage_rate': 0.5,
            'sign_template_id': cls.template.id,
            'contract_update_template_id': cls.template.id,
            'hr_responsible_id': cls.env.ref('base.user_admin').id,
            'company_id': cls.company_id.id,
            'meal_voucher_amount': 7.45,
            'fuel_card': 0,
            'internet': 38,
            'mobile': 30,
            'car_id': False,
            'l10n_be_lsa_monthly_pro_other_amount': 300,
            'l10n_be_joint_committee_id': cls.cp200.id,
        })

        cls.resource_calendar = cls.env['resource.calendar'].create({
            'name': 'Test Calendar',
            'company_id': cls.company_id.id,
            'hours_per_day': 7.6,
            'hours_per_week': 38,
            'full_time_required_hours': 38
        })

        cls.employee_georges = cls.create_employee({
            'name': 'Georges',
            'date_version': date(2020, 1, 1),
            'contract_date_start': date(2020, 1, 1),
            'contract_date_end': False,
        })

        cls.employee_a = cls.create_employee({
            'name': 'A',
            'date_version': date(2020, 1, 1),
            'contract_date_start': date(2020, 1, 1),
            'contract_date_end': False,
        })

    @classmethod
    def create_employee(cls, values):
        default_values = {
            'private_country_id': cls.env.ref('base.be').id,
            'resource_calendar_id': cls.resource_calendar.id,
            'company_id': cls.company_id.id,
            'marital': "single",
            'spouse_fiscal_status': "without_income",
            'disabled': False,
            'disabled_spouse_bool': False,
            'is_non_resident': False,
            'disabled_children_number': 0,
            'other_senior_dependent': 0,
            'other_dependents': 0,
            'other_juniors_dependent': 0,
            'other_disabled_juniors_dependent': 0,
            'structure_type_id': cls.env.ref('hr.structure_type_employee_cp200').id,
            'date_version': date.today(),
            'contract_date_start': date.today(),
            'contract_date_end': False,
            'wage': 2500.0,
            'hourly_wage': 0.0,
            'commission_on_target': 0.0,
            'fuel_card': 150.0,
            'internet': 38.0,
            'mobile': 30.0,
            'meal_voucher_amount': 7.45,
            'ip_wage_rate': 0,
            'has_bicycle': False,
            'l10n_be_lsa_monthly_pro_other_amount': 150,
            'l10n_be_joint_committee_id': cls.cp200.id,
        }
        default_values.update(values)
        employee = cls.env['hr.employee'].create(default_values)
        return employee
