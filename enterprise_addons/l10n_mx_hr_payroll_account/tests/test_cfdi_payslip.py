# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import date

from odoo.addons.l10n_mx_edi.tests.common import TestMxEdiCommon
from odoo.tests import tagged
from odoo.fields import Command


@tagged('post_install_l10n', 'post_install', '-at_install', *TestMxEdiCommon.extra_tags)
class TestMxEdiHrPayrollCommon(TestMxEdiCommon):

    _test_user_groups = (
        'hr_payroll.group_hr_payroll_manager',
        'account.group_account_invoice',  # Payroll user must be an invoice user
        'base.group_system',  # Needed for some configurations
    )

    _test_user_name = 'Test MX Payroll User'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids += cls.env.ref('hr_payroll.group_hr_payroll_officer')
        cls.company.partner_id.zip = '20000'
        cls.company.l10n_mx_imss_id = 'B5510768108'
        cls.company.vat = 'URE180429TM6'

        cls.partner_employee = cls.env['res.partner'].create({
            'name': "Ingrid Xodar Jimenez",
            'country_id': cls.env.ref('base.mx').id,
            'state_id': cls.env.ref('base.state_mx_jal').id,
        })

        cls.bank_account = cls.env['res.partner.bank'].create({
            'account_number': '1111111111',
            'clearing_label_id': cls.env.ref('base.clearing_label_mx').id,
            'clearing_number': '002',
            'bank_name': 'BANAMEX',
            'country_id': cls.env.ref('base.mx').id,
            'partner_id': cls.partner_employee.id,
        })

        cls.department = cls.env['hr.department'].create({
            'name': 'Desarrollo',
            'company_id': cls.company.id,
        })

        cls.job = cls.env['hr.job'].sudo().create({
            'name': 'Ingeniero de Software',
            'company_id': cls.company.id,
        })

        cls.employee = cls.env['hr.employee'].create({
            'name': 'Ingrid Xodar Jimenez',
            'company_id': cls.company.id,
            'bank_account_ids': cls.bank_account.ids,
            'l10n_mx_rfc': 'XOJI740919U48',
            'registration_number': '120',
            'l10n_mx_ssn': '000000',
            'l10n_mx_curp': 'XEXX010101HNEXXXA4',
            'private_zip': '76028',
            'work_contact_id': cls.partner_employee.id,
            'department_id': cls.department.id,
            'job_id': cls.job.id,
            'date_version': '2015-01-01',
            'contract_date_start': '2015-01-01',
            'l10n_mx_regime_type': '03',
            'employee_type_id': cls.env.ref('l10n_mx_hr_payroll_account.l10n_mx_contract_type_01').id,
            'wage': 50000,
            'schedule_pay': 'bi-weekly',
        })

        cls.employee.write({'review_state': '1_reviewed'})

        cls.structure_type = cls.env.ref('hr.structure_type_employee')
        cls.pay_structure = cls.env.ref('hr_payroll.default_structure')
        cls.us_company = cls.env['res.company'].create({
            'name': 'US Test Company',
            'country_id': cls.env.ref('base.us').id,
        })
        cls.us_employee = cls.env['hr.employee'].create({
            'name': 'John Doe',
            'company_id': cls.us_company.id,
            'date_version': '2024-01-01',
            'contract_date_start': '2024-01-01',
            'wage': 5000,
            'structure_type_id': cls.structure_type.id,
        })

    def _assert_payslip_cfdi(self, payslip, filename):
        document = payslip.l10n_mx_edi_document_ids.filtered(lambda x: x.state == 'payslip_sent')[:1]
        self.assertTrue(document)
        self._assert_document_cfdi(document, filename)

    def _generate_payslip_with_cfdi(self, date_from=None, date_to=None, property_inputs=None):
        if property_inputs is None:
            property_inputs = {}
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'date_from': date_from or '2026-05-01',
            'date_to': date_to or '2026-05-15',
            'struct_id': self.env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay').id,
        })
        payslip._set_input_values(property_inputs)
        payslip.compute_sheet()

        payslip.action_payslip_done()
        payslip.move_id.action_post()
        payslip.action_payslip_paid()
        with self.mx_external_setup(self.frozen_today), self.with_mocked_pac_sign_success():
            payslip._l10n_mx_edi_cfdi_try_send()
        return payslip

    def test_cfdi_nomina(self):
        payslip = self._generate_payslip_with_cfdi()
        self._assert_payslip_cfdi(payslip, 'test_cfdi_nomina')

    def test_cfdi_nomina_with_clabe(self):
        self.bank_account.account_number = '002010077777777771'
        payslip = self._generate_payslip_with_cfdi()
        self._assert_payslip_cfdi(payslip, 'test_cfdi_nomina_with_clabe')

    def test_cfdi_nomina_curp_emisor(self):
        self.company.l10n_mx_edi_fiscal_regime = '621'
        self.company.vat = 'CACX7605101P8'
        self.company.l10n_mx_curp = 'CACX760431HNESHC03'
        payslip = self._generate_payslip_with_cfdi()
        self._assert_payslip_cfdi(payslip, 'test_cfdi_nomina_curp_emisor')

    def test_cfdi_nomina_con_bonos_fondo_ahorro_y_deducciones(self):
        self.employee.l10n_mx_savings_fund = 500
        self.employee.write({'review_state': '1_reviewed'})
        payslip = self._generate_payslip_with_cfdi(
            property_inputs={
                'BONUS': 150,
            },
        )
        self._assert_payslip_cfdi(payslip, 'test_cfdi_nomina_con_bonos_fondo_ahorro_y_deducciones')

    def test_cfdi_nomina_con_incapacidades(self):
        self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'work_entry_type_id': self.env.ref('hr_work_entry.l10n_mx_work_entry_type_work_risk_imss').id,
            'request_date_from': '2026-05-04',
            'request_date_to': '2026-05-08',
        })
        payslip = self._generate_payslip_with_cfdi()
        self._assert_payslip_cfdi(payslip, 'test_cfdi_nomina_con_incapacidades')

    def test_cfdi_nomina_con_septimo_dia(self):
        self.employee.write({
            'wage': 7000.0,
            'schedule_pay': 'weekly',
            'l10n_mx_is_seventh_day': True,
            'resource_calendar_id': self.env.ref('l10n_mx_hr_payroll.resource_calendar_def_48h').id,
        })
        self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'work_entry_type_id': self.env.ref('hr_work_entry.mx_work_entry_type_unpaid_leave').id,
            'request_date_from': '2026-06-04',
            'request_date_to': '2026-06-04',
        })
        payslip = self._generate_payslip_with_cfdi(date(2026, 6, 1), date(2026, 6, 7))
        self._assert_payslip_cfdi(payslip, 'test_cfdi_nomina_con_septimo_dia')

    def test_cfdi_primary_false_for_non_mx_payrun(self):
        """
        Test that l10n_mx_cfdi_primary returns False for payruns
        that contain only non-Mexican payslips.
        """
        self.env.user.company_ids = [Command.link(self.us_company.id)]
        payslip_run = self.env['hr.payslip.run'].create({
            'date_start': date(2024, 1, 1),
            'date_end': date(2024, 1, 31),
            'name': 'US Payslip Run',
            'company_id': self.us_company.id,
            'structure_id': self.pay_structure.id,
        })

        # Creating the payslip links it to the payrun via payslip_run_id, populating slip_ids
        self.env['hr.payslip'].create({
            'employee_id': self.us_employee.id,
            'date_from': date(2024, 1, 1),
            'date_to': date(2024, 1, 31),
            'payslip_run_id': payslip_run.id,
            'company_id': self.us_company.id,
        })

        self.assertEqual(len(payslip_run.slip_ids), 1)

        self.assertFalse(
            payslip_run.l10n_mx_cfdi_primary,
            "l10n_mx_cfdi_primary should be False for payruns without Mexican payslips"
        )

        self.assertFalse(
            payslip_run.l10n_mx_cfdi_secondary,
            "l10n_mx_cfdi_secondary should be False for payruns without Mexican payslips"
        )

    def test_cfdi_nomina_sat_state_update(self):
        payslip = self._generate_payslip_with_cfdi()
        document = payslip.l10n_mx_edi_document_ids
        self.assertRecordValues(document, [{'sat_state': 'not_defined'}])

        with self.mx_external_setup(self.frozen_today), self.with_mocked_sat_call(lambda _x: 'valid'):
            payslip.l10n_mx_edi_cfdi_try_sat()

        self.assertRecordValues(document, [{'sat_state': 'valid'}])
