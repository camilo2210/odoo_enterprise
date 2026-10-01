from freezegun import freeze_time
from datetime import date


from odoo import Command
import odoo.tests


@odoo.tests.tagged('-at_install', 'post_install', 'salary')
class TestEmployeeSalaryConfigurator(odoo.tests.HttpCase):
    @classmethod
    @freeze_time('2022-01-01 09:00:00')
    def setUpClass(cls):
        super().setUpClass()

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
        type_employee_name, type_city, type_country_name, type_street = cls.env['sign.item.type'].create([
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
            },
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
            }
        ])
        cls.company_id = cls.env['res.company'].create({
            'name': 'Rambo Company - TEST',
            'country_id': False,
        })

        img_content = cls.file_read('sign/static/demo/signature.png')

        cls.env.ref('base.user_admin').write({
            'company_ids': [(4, cls.company_id.id)],
            'company_id': cls.company_id.id,
            'name': 'Mitchell Admin',
            'sign_signature': img_content,
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
            'company_id': cls.company_id.id,
        })
        cls.env.ref('base.main_partner').email = "info@yourcompany.example.com"

        cls.senior_dev_contract = cls.env['hr.version'].create({
            'name': 'Senior Developer Template Contract',
            'wage': 6000,
            'structure_type_id': cls.env.ref('hr.structure_type_employee').id,
            'sign_template_id': cls.template.id,
            'contract_update_template_id': cls.template.id,
            'hr_responsible_id': cls.env.ref('base.user_admin').id,
            'company_id': cls.company_id.id,
        })

        cls.recruiter_employee = cls.env['hr.employee'].create({
            'name': 'Adam Employston',
            'company_id': cls.company_id.id,
            'user_id': cls.env.ref('base.user_admin').id,
        })

        cls.job = cls.env['hr.job'].create({
            'name': 'Senior Developer BE',
            'company_id': cls.company_id.id,
            'contract_template_id': cls.senior_dev_contract.id,
            'recruiter_id': cls.recruiter_employee.id,
        })
        cls.work_location = cls.env['hr.work.location'].create({
            'name': "Office 1",
            'location_type': "office",
            'address_id': cls.env.company.partner_id.id,
            })
        cls.employee_1 = cls.env['hr.employee'].create({
            'name': 'Ahmed Abdelrazek',
            'work_location_id': cls.work_location.id,
            'date_version': date(2020, 1, 1),
            'contract_date_start': date(2020, 1, 1),
            'contract_date_end': False,
            'employee_type_id': cls.env.ref('hr.contract_type_employee').id,
            'company_id': cls.company_id.id,
            'job_id': cls.job.id,
            'sign_template_id': cls.template.id,
            'contract_update_template_id': cls.template.id,
            'hr_responsible_id': cls.env.ref('base.user_admin').id,
            'work_email': 'ahmed.abdelrazek@test_email.com',
            'private_country_id': cls.env.ref('base.be').id,
            'private_state_id': cls.env.ref('base.state_be_1').id,
            'wage': 6000,
        })

    def test_employee_salary_configurator_amendment_flow(self):
        employee = self.employee_1

        with freeze_time("2022-01-01 12:00:00"):
            self.start_tour("/odoo", 'hr_contract_salary_employee_flow_tour', login='admin', timeout=350)
            offers = self.env['hr.contract.salary.offer'].search([('employee_id', '=', employee.id)])
            self.assertTrue(offers)
            latest_offer = offers[-1]
            self.assertTrue(latest_offer.is_contract_amendment)

        with freeze_time("2022-01-01 13:00:00"):
            self.start_tour("/odoo", 'hr_contract_salary_employee_flow_tour_counter_sign', login='admin', timeout=350)
            versions = employee.version_ids
            self.assertEqual(len(versions), 2)
            previous_version = versions[-2]
            amendment_version = versions[-1]
            self.assertEqual(amendment_version.contract_date_start, date(2020, 1, 1))
            self.assertEqual(amendment_version.date_version, date(2022, 1, 1))
            self.assertFalse(amendment_version.contract_date_end)
            self.assertFalse(previous_version.contract_date_end)

    def test_employee_salary_configurator_new_contract_flow(self):
        employee = self.employee_1
        employee.version_id.contract_date_end = date(2022, 6, 1)

        with freeze_time("2023-01-01 10:00:00"):
            self.start_tour("/odoo", 'hr_contract_salary_employee_flow_tour', login='admin', timeout=350)
            offers = self.env['hr.contract.salary.offer'].search([('employee_id', '=', employee.id)])
            self.assertTrue(offers)
            new_contract_offer = offers.sorted('create_date')[-1]
            self.assertFalse(new_contract_offer.is_contract_amendment)

        with freeze_time("2023-01-01 11:00:00"):
            self.start_tour("/odoo", 'hr_contract_salary_employee_flow_tour_counter_sign', login='admin', timeout=350)
            final_contract = self.env['hr.version'].search([('employee_id', '=', employee.id)], order='date_version desc', limit=1)
            self.assertEqual(final_contract.contract_date_start, date(2023, 1, 1))
            self.assertEqual(final_contract.date_version, date(2023, 1, 1))
            self.assertFalse(final_contract.contract_date_end)

    def test_employee_salary_configurator_radio_benefit_preselection(self):
        benefit_type = self.env['hr.contract.salary.benefit.type'].create({'name': 'Salary'})
        self.env['hr.contract.salary.benefit'].create({
            'name': 'Gross Wage',
            'is_configurable_benefit': True,
            'benefit_type_id': benefit_type.id,
            'res_field_id': self.env.ref('hr_payroll.field_hr_version__wage').id,
            'display_type': 'radio',
            'structure_type_id': self.senior_dev_contract.structure_type_id.id,
            'value_ids': [
                Command.create({'name': 'No', 'value': '0'}),
                Command.create({'name': 'Yes', 'value': '1'}),
            ],
        })
        offer = self.env['hr.contract.salary.offer'].create({
            'contract_template_id': self.senior_dev_contract.id,
            'employee_id': self.employee_1.id,
        })
        self.authenticate('admin', 'admin')
        url = f'/salary_package/simulation/offer/{offer.id}'
        res = self.url_open(url)
        self.assertEqual(res.status_code, 200)
        self.assertIn('name="wage_radio" data-value="1" checked="True"', res.text)
