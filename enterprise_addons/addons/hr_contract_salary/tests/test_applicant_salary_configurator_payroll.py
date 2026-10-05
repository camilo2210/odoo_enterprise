import json

from freezegun import freeze_time

from odoo import fields
from odoo.tests import Form, HttpCase, tagged

from odoo.addons.mail.tests.common import mail_new_test_user


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
        pdf_content = cls.file_read('hr_contract_salary/static/src/demo/employee_contract.pdf')
        cls.pdf_content = pdf_content.content

        attachment = cls.env['ir.attachment'].create({
            'type': 'binary',
            'raw': pdf_content,
            'name': 'test_employee_contract.pdf',
        })

        cls.template = cls.env['sign.template'].create({})

        cls.document_id = cls.env['sign.document'].create({
            'attachment_id': attachment.id,
            'template_id': cls.template.id,
        })

        cls.env['sign.item'].create([
            {
                'type_id': cls.env.ref('sign.sign_item_type_text').id,
                'name': 'employee_id.name',
                'required': True,
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
                'type_id': cls.env.ref('sign.sign_item_type_text').id,
                'name': 'private_city',
                'required': True,
                'responsible_id': cls.env.ref('hr_sign.sign_item_role_employee_signatory').id,
                'page': 1,
                'posX': 0.506,
                'posY': 0.184,
                'document_id': cls.document_id.id,
                'width': 0.150,
                'height': 0.015,
            }, {
                'type_id': cls.env.ref('sign.sign_item_type_text').id,
                'name': 'private_country_id.name',
                'required': True,
                'responsible_id': cls.env.ref('hr_sign.sign_item_role_employee_signatory').id,
                'page': 1,
                'posX': 0.663,
                'posY': 0.184,
                'document_id': cls.document_id.id,
                'width': 0.150,
                'height': 0.015,
            }, {
                'type_id': cls.env.ref('sign.sign_item_type_text').id,
                'name': 'private_street',
                'required': True,
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

        cls.env.ref('base.user_admin').write({
            'company_ids': [(4, cls.company_id.id)],
            'company_id': cls.company_id.id,
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
            'company_id': cls.company_id.id,
        })
        demo.write({
            'partner_id': partner_id,
            'company_id': cls.company_id.id,
            'company_ids': [(4, cls.company_id.id)]
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

        cls.senior_dev_job = cls.env['hr.job'].create({
            'name': 'Senior Developer BE',
            'company_id': cls.company_id.id,
            'contract_template_id': cls.senior_dev_contract.id,
        })

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
            offer_form.budget_type = 'yearly_employer'
            self.assertEqual(offer_form.salary_amount, 12000)
            self.assertTrue(offer_form.job_title, self.senior_dev_job.name)
            self.assertTrue(offer_form.contract_start_date, fields.Date.today())
            self.assertTrue(offer_form.employee_id, new_version.employee_id)
