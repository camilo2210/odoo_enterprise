from freezegun import freeze_time
import json
from odoo import fields
from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.tests import Form, HttpCase, tagged


@tagged('-at_install', 'post_install', 'salary')
class TestSalaryConfiguratorForApplicant(HttpCase):
    @classmethod
    @freeze_time('2022-01-01 09:00:00')
    def setUpClass(cls):
        super().setUpClass()

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
        type_employee_name, type_city, type_country_name, type_street = cls.env['sign.item.type'].create([
            {
                'name': 'Employee Name',
                'placeholder': 'legal_name',
                'item_type': 'text',
                'model_id': version_model.id,
                'auto_field': 'employee_id.legal_name',
                'constant': True,
             },
            {
                'name': 'Private City',
                'placeholder': 'City',
                'item_type': 'text',
                'model_id': version_model.id,
                'auto_field': 'private_city',
                'constant': True,
            },
            {
                'name': 'Country',
                'placeholder': 'Country',
                'item_type': 'text',
                'model_id': version_model.id,
                'auto_field': 'private_country_id.name',
                'constant': True,
            },
            {
                'name': 'Street',
                'placeholder': 'Street',
                'item_type': 'text',
                'model_id': version_model.id,
                'auto_field': 'private_street',
                'constant': True,
            },
        ])
        cls.env['sign.item'].create([
            {
                'type_id': type_employee_name.id,
                'name': 'Employee Name',
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
            'name': 'My Belgian Company - TEST',
            'country_id': cls.env.ref('base.be').id,
        })

        hr_user = mail_new_test_user(
            cls.env,
            email='hr@test.example.com',
            groups='hr_recruitment.group_hr_recruitment_user,sign.group_sign_user,hr.group_hr_user',
            login='hr_demo',
            name="HR officer",
        )
        hr_user.write({
            'company_ids': [(4, cls.company_id.id)],
        })

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
        demo.write({
            'partner_id': partner_id,
            'company_id': cls.company_id.id,
            'company_ids': [(4, cls.company_id.id)]
        })
        cls.env.ref('base.main_partner').email = "info@yourcompany.example.com"

        cls.new_dev_contract = cls.env['hr.version'].create({
            'name': 'New Developer Template Contract',
            'wage': 3000,
            'structure_type_id': cls.env.ref('hr.structure_type_employee').id,
            'sign_template_id': cls.template.id,
            'contract_update_template_id': cls.template.id,
            'hr_responsible_id': cls.env.ref('base.user_admin').id,
        })

        cls.senior_dev_contract = cls.env['hr.version'].create({
            'name': 'Senior Developer Template Contract',
            'wage': 6000,
            'structure_type_id': cls.env.ref('hr.structure_type_employee').id,
            'sign_template_id': cls.template.id,
            'contract_update_template_id': cls.template.id,
            'hr_responsible_id': cls.env.ref('base.user_admin').id,
            'company_id': cls.company_id.id,
        })

        cls.senior_dev_job = cls.env['hr.job'].create({
            'name': 'Senior Developer BE',
            'company_id': cls.company_id.id,
            'contract_template_id': cls.senior_dev_contract.id,
        })

    def test_applicant_salary_configurator_flow(self):
        with freeze_time("2022-01-01 12:00:00"):
            self.start_tour("/odoo", 'hr_contract_salary_applicant_flow_tour', login='hr_demo', timeout=350)
            employee = self.env['hr.employee'].search([('name', 'ilike', 'Mitchell Admin 3'), ('active', '=', False)])
            active_versions = self.env['hr.version'].search([('employee_id', '=', employee.id), ('active', '=', True)])
            archived_versions = self.env['hr.version'].search([('employee_id', '=', employee.id), ('active', '=', False)])
            self.assertEqual(len(active_versions), 1, "Exactly one active version should have been created.")
            self.assertEqual(len(archived_versions), 1, "Exactly one archived version should have been created.")
            self.assertEqual(active_versions.wage, 0, "The active version should be a dummy version")
            self.assertEqual(archived_versions.wage, 6000.0, "The archived version should be the one from the offer")

            self.assertTrue(employee, 'An employee has been created')
            self.assertFalse(employee.active, 'Employee is not active')

        with freeze_time("2022-01-01 13:00:00"):
            self.start_tour("/odoo", 'hr_contract_salary_applicant_flow_tour_counter_sign', login='admin', timeout=350)
            employee = self.env['hr.employee'].search([('name', 'ilike', 'Mitchell Admin 3')])
            active_versions = self.env['hr.version'].search([('employee_id', '=', employee.id), ('active', '=', True)])
            archived_versions = self.env['hr.version'].search([('employee_id', '=', employee.id), ('active', '=', False)])
            self.assertEqual(active_versions.wage, 6000.0, "The active version should be the one from the offer")
            self.assertEqual(archived_versions.wage, 0, "The archived version should be a dummy version")

            self.assertTrue(employee.active, 'Employee is active')

    def test_applicant_offer_form(self):
        applicant = self.env['hr.applicant'].create({
            'partner_name': 'Test app',
            'job_id': self.senior_dev_job.id,
        })
        applicant.action_generate_offer()
        offer = self.env['hr.contract.salary.offer'].search([('applicant_id', '=', applicant.id)])
        data = {
            "params": {
                "offer_id": offer.id,
                "benefits": {
                    'version': {
                        'wage': 1000,
                        'final_yearly_costs': 12000,
                        'holidays': 10,
                    },
                    'version_personal': {
                        'private_city': "Louvain-La-Neuve",
                        'private_country_id': self.env.ref("base.be").id,
                        'private_street': "58 rue des Wallons",
                    },
                    'employee': {
                        'name': 'New Employee',
                        'private_email': 'new_employee@test.example.com',
                        'employee_job_id': self.senior_dev_job.id,
                        'department_id': None,
                        'job_title': self.senior_dev_job.name,
                    },
                    'address': {},
                    'bank_account': {},
                },
                "token": offer.access_token,
            }
        }
        res = self.url_open("/salary_package/submit", json=data)
        content = json.loads(res.content)
        new_version = self.env['hr.version'].browse(content['result']['new_version_id'])
        new_version.action_generate_offer()
        new_offer = self.env['hr.contract.salary.offer'].search([('employee_version_id', '=', new_version.id)])
        with Form(new_offer) as offer_form:
            self.assertEqual(offer_form.contract_template_id, new_version)
            self.assertEqual(offer_form.sign_template_id, offer_form.contract_template_id.sign_template_id)
            if 'final_yearly_costs' in offer_form._view['fields']:
                # In hr_contract_salary_payroll module, the field is removed from the view and replaced by salary_amount and budget_type
                # This test has been duplicated in hr_contract_salary_payroll module to cover both cases.
                self.assertEqual(offer_form.final_yearly_costs, 12000)
            self.assertTrue(offer_form.job_title, self.senior_dev_job.name)
            self.assertTrue(offer_form.contract_start_date, fields.Date.today())

    def test_deleting_partial_signed_offer_should_not_delete_employee(self):
        self.start_tour("/odoo", 'hr_contract_salary_applicant_flow_tour', login='admin', timeout=350)
        self.start_tour("/odoo", 'hr_contract_salary_applicant_flow_tour_counter_sign', login='admin', timeout=350)
        self.start_tour("/odoo", 'hr_contract_salary_applicant_flow_tour', login='admin', timeout=350)
        applicant = self.env['hr.applicant'].search([('partner_name', 'ilike', 'Mitchell Admin 3')])
        offers = self.env['hr.contract.salary.offer'].search([('applicant_id', 'in', applicant.ids), ('state', '=', 'half_signed')])
        offers.unlink()
        employee = self.env['hr.employee'].search([('name', 'ilike', 'Mitchell Admin 3'), ('active', '=', True)])
        self.assertTrue(employee, "The employee should not be deleted")

    def _create_sign_values(self, sign_item_ids, role_id):
        return {
            str(sign_id): 'a'
            for sign_id in sign_item_ids.filtered(
                lambda r: not r.responsible_id or r.responsible_id.id == role_id
            ).mapped('id')
        }

    def test_open_contract_on_offer_signed_multiple_times(self):
        applicant = self.env['hr.applicant'].create({
            'partner_name': 'Test app',
            'job_id': self.senior_dev_job.id,
        })
        applicant.action_generate_offer()
        offer = self.env['hr.contract.salary.offer'].search([('applicant_id', '=', applicant.id)])
        data = {
            "params": {
                "offer_id": offer.id,
                "benefits": {
                    'version': {
                        'wage': 1000,
                        'final_yearly_costs': 12000,
                        'holidays': 10,
                    },
                    'version_personal': {
                        'private_city': "Louvain-La-Neuve",
                        'private_country_id': self.env.ref("base.be").id,
                        'private_street': "58 rue des Wallons",
                    },
                    'employee': {
                        'name': 'New Employee',
                        'private_email': 'new_employee@test.example.com',
                        'employee_job_id': self.senior_dev_job.id,
                        'department_id': None,
                        'job_title': self.senior_dev_job.name,
                    },
                    'address': {},
                    'bank_account': {},
                },
                "token": offer.access_token,
            },
        }

        # applicant signs for the first time
        res_1 = self.url_open("/salary_package/submit", json=data)
        content_1 = json.loads(res_1.content)
        sign_request_1 = self.env['sign.request'].browse(content_1['result']['request_id'])
        sign_request_1.template_id.sign_item_ids.write({'required': False})
        sign_data_applicant_1 = {
            'signature': self._create_sign_values(
                sign_request_1.template_id.sign_item_ids,
                self.env.ref('hr_sign.sign_item_role_employee_signatory').id,
            ),
        }
        self.url_open(
            '/sign/sign/%d/%s' % (sign_request_1.id, content_1['result']['token']),
            data=json.dumps(sign_data_applicant_1),
            headers={'Content-Type': 'application/json'},
        )

        # applicant signs for the second time
        res_2 = self.url_open("/salary_package/submit", json=data)
        content_2 = json.loads(res_2.content)
        sign_request_2 = self.env['sign.request'].browse(content_2['result']['request_id'])
        sign_request_2.template_id.sign_item_ids.write({'required': False})
        sign_data_applicant_2 = {
            'signature': self._create_sign_values(
                sign_request_1.template_id.sign_item_ids,
                self.env.ref('hr_sign.sign_item_role_employee_signatory').id,
            ),
        }
        self.url_open(
            '/sign/sign/%d/%s' % (sign_request_2.id, content_2['result']['token']),
            data=json.dumps(sign_data_applicant_2),
            headers={'Content-Type': 'application/json'},
        )

        # hr signs counter signs the second sign request
        sign_data_hr = {
            'signature': self._create_sign_values(
                sign_request_2.template_id.sign_item_ids,
                self.env.ref('hr_sign.sign_item_role_job_responsible').id,
            ),
        }
        self.url_open(
            '/sign/sign/%d/%s' % (sign_request_2.id, content_2['result']['token']),
            data=json.dumps(sign_data_hr),
            headers={'Content-Type': 'application/json'},
        )

        # check that the smart button redirects to the correct version
        action = offer.action_view_version()
        redirected_version_id = action['context']['version_id']
        self.assertEqual(
            redirected_version_id,
            content_2['result']['new_version_id'],
            "action_view_version() should redirect to the fully signed contract and not to the partially signed archived one",
        )
