# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time
from datetime import date, datetime
from unittest.mock import MagicMock, patch

from freezegun import freeze_time

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.l10n_be_hr_payroll.models.certificate import CertificateCertificate
from odoo.addons.l10n_be_hr_payroll.models.hr_version import HrVersion
from odoo.addons.l10n_be_hr_payroll.models.utils import xml_str_to_dict
from odoo.addons.l10n_be_hr_payroll.tests.common import TestPayrollCommon
from odoo.addons.mail.tests.common import mail_new_test_user


@tagged('post_install', '-at_install', 'post_install_l10n')
@patch.object(CertificateCertificate, '_decode_certificate_for_be_onss_xml', lambda contract, xml_str: b'dummy\r\nsignature\r\n')
class TestFlexiAtWork(TestPayrollCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # hr_version.write() auto-triggers a real Dimona submission when l10n_be_needs_dimona_in
        # flips. This suite does not test Dimona submission, so stub it out for the whole class.
        dimona_patcher = patch.object(HrVersion, 'action_open_dimona', lambda self: None)
        dimona_patcher.start()
        cls.addClassCleanup(dimona_patcher.stop)

        cls.structure = cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary')

        cls.belgian_company = cls.create_belgian_company()
        cls.env.user.company_ids |= cls.belgian_company
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.belgian_company.ids))

        cls.belgian_company.write({
            'onss_certificate_id': cls.env['certificate.certificate'].create({}).id,
        })
        cls.belgian_company.current_payroll_config_id.write({
            'l10n_be_employer_category_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_employer_category_00050').id,
            'onss_registration_number': '125482497',
        })

        cls.payroll_manager = mail_new_test_user(
            cls.env, login='flx_payroll_mgr',
            groups='hr_payroll.group_hr_payroll_manager',
            company_id=cls.belgian_company.id,
            company_ids=[(4, cls.belgian_company.id)],
        )

        cls.flexi_employee = cls.create_flexi_employee({
            'name': 'Default Flexi Employee',
            'niss': '93051822361',
            'date_version': date(2026, 1, 1),
            'contract_date_start': date(2026, 1, 1),
            'l10n_be_flexi_monthly_wage': 384.76,
            'l10n_be_joint_committee_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_201').id,
            'l10n_be_worker_code_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00450').id,
        })

    @classmethod
    def create_flexi_employee(cls, values=None):
        defaults = {
            'name': 'Test Flexi Employee',
            'niss': '93051822361',
            'date_version': date(2026, 1, 1),
            'contract_date_start': date(2026, 1, 1),
            'l10n_be_flexi_monthly_wage': 384.76,
            'l10n_be_joint_committee_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_201').id,
            'l10n_be_worker_code_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00450').id,
            'l10n_be_dimona_category': 'flx',
            'fuel_card': 0.0,
            'internet': 0.0,
            'mobile': 0.0,
            'laptop': 0.0,
            'l10n_be_lsa_monthly_pro_other_amount': 0.0,
            'meal_voucher_amount': 0.0,
            'has_bicycle': False,
        }
        defaults.update(values or {})
        return cls.create_employee(defaults)

    def create_slip(self, employee, date_from, date_to, commission=0.0):
        slip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'struct_id': self.structure.id,
            'version_id': employee.version_id.id,
            'date_from': date_from,
            'date_to': date_to,
        })
        if commission:
            slip._set_input_value('COMMISSION', commission)
        slip.compute_sheet()
        slip.action_payslip_done()
        return slip

    @staticmethod
    def fake_time_object():
        today = datetime.now()
        day = today.strftime('%Y%m%d')
        hour = today.strftime('%H:%M:%S.%f')[:-3]
        return patch.object(time, 'strftime', lambda fmt, t: day if fmt == '%Y%m%d' else hour)

    def generate_flxwage_declaration(self, payslip, environment='T', skip_signature=True):
        declaration = self.env['l10n.be.flexi.at.work'].with_user(self.payroll_manager).create({
            'payslip_id': payslip.id,
            'environment': environment,
        })
        with self.fake_time_object():
            declaration.with_context(onss_skip_signature=skip_signature).generate_declaration_xml_report()
        self.assertFalse(declaration.error_message)
        self.assertEqual(declaration.state, 'ready')
        return declaration

    def test_not_done_payslip(self):
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.flexi_employee.id,
            'struct_id': self.structure.id,
            'version_id': self.flexi_employee.version_id.id,
            'date_from': date(2026, 1, 1),
            'date_to': date(2026, 1, 31),
        })
        with self.assertRaises(UserError):
            self.generate_flxwage_declaration(payslip)

    def test_not_flexi_employee(self):
        non_flexi_employee = self.create_employee({
            'name': 'Test Non-Flexi Employee',
            'date_version': date(2026, 1, 1),
            'contract_date_start': date(2026, 1, 1),
            'wage': 2500.0,
        })
        payslip = self.create_slip(non_flexi_employee, date(2026, 1, 1), date(2026, 1, 31))
        with self.assertRaises(UserError):
            self.generate_flxwage_declaration(payslip)

    def test_duplicate_declaration_raises(self):
        payslip = self.create_slip(self.flexi_employee, date(2026, 1, 1), date(2026, 1, 31))
        self.generate_flxwage_declaration(payslip)
        with self.assertRaises(Exception), mute_logger('odoo.sql_db'):
            self.generate_flxwage_declaration(payslip)

    @freeze_time('2025-12-31')
    def test_declaration_december_2025(self):
        employee = self.create_flexi_employee({
            'name': 'Docx Flexi Employee',
            'niss': '93051822361',
            'date_version': date(2025, 12, 1),
            'contract_date_start': date(2025, 12, 1),
            'l10n_be_flexi_monthly_wage': 87.30,
            'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_302').id,
            'l10n_be_worker_code_id': self.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00050').id,
        })
        slip = self.create_slip(employee, date(2025, 12, 1), date(2025, 12, 31))

        declaration = self.generate_flxwage_declaration(slip)
        flxwage_dict = xml_str_to_dict(declaration.xml_file.content)
        expected_dict = {'FLXWAGE': {'@{http://www.w3.org/2001/XMLSchema-instance}schemaLocation': 'http://socialsecurity.be/xml/ns/FLXWAGE FLXWAGE_20253.xsd', 'Form': {'Identification': 'FLXWAGE', 'FormCreationDate': '2025-12-31', 'FormCreationHour': '00:00:00.000', 'AttestationStatus': '0', 'TypeForm': 'SU', 'Debtor': {'CompanyID': '0897223670', 'NOSSRegistrationNbr': '125482497', 'Beneficiary': {'INSS': '93051822361', 'Relation': {'RelationType': '1', 'Reference': {'ReferenceType': '10', 'ReferenceOrigin': '8', 'ReferenceNbr': declaration.name}, 'Calculation': {'CalculationPeriodStartingDate': '2025-12-01', 'CalculationPeriodEndingDate': '2025-12-31', 'CalculationDate': '2025-12-31', 'Features': {'ValidityPeriodStartingDate': '2025-12-01', 'ValidityPeriodEndingDate': '2025-12-31', 'EmployerClass': '050', 'WorkerCode': '050', 'FinancialElement': {'FinancialElementType': '1', 'FinancialElementCode': '0001001000', 'Amount': '9400'}}}}}}}}}
        self.assertDictEqual(expected_dict, flxwage_dict)

    @freeze_time('2026-04-30')
    def test_declaration_april_2026(self):
        employee = self.create_flexi_employee({
            'name': 'Docx Flexi Employee',
            'niss': '93051822361',
            'date_version': date(2026, 4, 1),
            'contract_date_start': date(2026, 4, 1),
            'l10n_be_flexi_monthly_wage': 2171.00,
            'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_201').id,
            'l10n_be_worker_code_id': self.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00450').id,
        })
        slip = self.create_slip(employee, date(2026, 4, 1), date(2026, 4, 30), commission=102.09)

        declaration = self.generate_flxwage_declaration(slip)
        flxwage_dict = xml_str_to_dict(declaration.xml_file.content)
        expected_dict = {'FLXWAGE': {'@{http://www.w3.org/2001/XMLSchema-instance}schemaLocation': 'http://socialsecurity.be/xml/ns/FLXWAGE FLXWAGE_20261.xsd', 'Form': {'Identification': 'FLXWAGE', 'FormCreationDate': '2026-04-30', 'FormCreationHour': '00:00:00.000', 'AttestationStatus': '0', 'TypeForm': 'SU', 'Debtor': {'CompanyID': '0897223670', 'NOSSRegistrationNbr': '125482497', 'Beneficiary': {'INSS': '93051822361', 'Relation': {'RelationType': '1', 'Reference': {'ReferenceType': '10', 'ReferenceOrigin': '8', 'ReferenceNbr': declaration.name}, 'Calculation': {'CalculationPeriodStartingDate': '2026-04-01', 'CalculationPeriodEndingDate': '2026-04-30', 'CalculationDate': '2026-04-30', 'Features': {'ValidityPeriodStartingDate': '2026-04-01', 'ValidityPeriodEndingDate': '2026-04-30', 'EmployerClass': '050', 'WorkerCode': '450', 'FinancialElement': [{'FinancialElementType': '1', 'FinancialElementCode': '0002001000', 'Amount': '10992'}, {'FinancialElementType': '1', 'FinancialElementCode': '0001001000', 'Amount': '233752'}]}}}}}}}}
        self.assertDictEqual(expected_dict, flxwage_dict)

    @freeze_time('2026-05-31')
    def test_declaration_may_2026(self):
        employee = self.create_flexi_employee({
            'name': 'Docx Flexi Employee',
            'niss': '93051822361',
            'date_version': date(2026, 5, 1),
            'contract_date_start': date(2026, 5, 1),
            'l10n_be_flexi_monthly_wage': 367.04,
            'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_302').id,
            'l10n_be_worker_code_id': self.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00050').id,
        })
        slip = self.create_slip(employee, date(2026, 5, 1), date(2026, 5, 31))

        declaration = self.generate_flxwage_declaration(slip)
        flxwage_dict = xml_str_to_dict(declaration.xml_file.content)
        expected_dict = {'FLXWAGE': {'@{http://www.w3.org/2001/XMLSchema-instance}schemaLocation': 'http://socialsecurity.be/xml/ns/FLXWAGE FLXWAGE_20261.xsd', 'Form': {'Identification': 'FLXWAGE', 'FormCreationDate': '2026-05-31', 'FormCreationHour': '00:00:00.000', 'AttestationStatus': '0', 'TypeForm': 'SU', 'Debtor': {'CompanyID': '0897223670', 'NOSSRegistrationNbr': '125482497', 'Beneficiary': {'INSS': '93051822361', 'Relation': {'RelationType': '1', 'Reference': {'ReferenceType': '10', 'ReferenceOrigin': '8', 'ReferenceNbr': declaration.name}, 'Calculation': {'CalculationPeriodStartingDate': '2026-05-01', 'CalculationPeriodEndingDate': '2026-05-31', 'CalculationDate': '2026-05-31', 'Features': {'ValidityPeriodStartingDate': '2026-05-01', 'ValidityPeriodEndingDate': '2026-05-31', 'EmployerClass': '050', 'WorkerCode': '050', 'FinancialElement': {'FinancialElementType': '1', 'FinancialElementCode': '0001001000', 'Amount': '39519'}}}}}}}}}
        self.assertDictEqual(expected_dict, flxwage_dict)

    @freeze_time('2026-06-30')
    def test_declaration_june_2026(self):
        employee = self.create_flexi_employee({
            'name': 'Docx Flexi Employee',
            'niss': '93051822361',
            'date_version': date(2026, 6, 1),
            'contract_date_start': date(2026, 6, 1),
            'l10n_be_flexi_monthly_wage': 384.76,
            'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_201').id,
            'l10n_be_worker_code_id': self.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00450').id,
        })
        slip = self.create_slip(employee, date(2026, 6, 1), date(2026, 6, 30))

        declaration = self.generate_flxwage_declaration(slip)
        flxwage_dict = xml_str_to_dict(declaration.xml_file.content)
        expected_dict = {'FLXWAGE': {'@{http://www.w3.org/2001/XMLSchema-instance}schemaLocation': 'http://socialsecurity.be/xml/ns/FLXWAGE FLXWAGE_20261.xsd', 'Form': {'Identification': 'FLXWAGE', 'FormCreationDate': '2026-06-30', 'FormCreationHour': '00:00:00.000', 'AttestationStatus': '0', 'TypeForm': 'SU', 'Debtor': {'CompanyID': '0897223670', 'NOSSRegistrationNbr': '125482497', 'Beneficiary': {'INSS': '93051822361', 'Relation': {'RelationType': '1', 'Reference': {'ReferenceType': '10', 'ReferenceOrigin': '8', 'ReferenceNbr': declaration.name}, 'Calculation': {'CalculationPeriodStartingDate': '2026-06-01', 'CalculationPeriodEndingDate': '2026-06-30', 'CalculationDate': '2026-06-30', 'Features': {'ValidityPeriodStartingDate': '2026-06-01', 'ValidityPeriodEndingDate': '2026-06-30', 'EmployerClass': '050', 'WorkerCode': '450', 'FinancialElement': {'FinancialElementType': '1', 'FinancialElementCode': '0001001000', 'Amount': '41427'}}}}}}}}}
        self.assertDictEqual(expected_dict, flxwage_dict)

    @freeze_time('2026-04-15')
    def test_num_suite_increments(self):
        payslips = self.env['hr.payslip'].create([
            {
                'name': 'Test Flexi Payslip February 2026',
                'employee_id': self.flexi_employee.id,
                'struct_id': self.structure.id,
                'version_id': self.flexi_employee.version_id.id,
                'date_from': date(2026, 2, 1),
                'date_to': date(2026, 2, 28),
            },
            {
                'name': 'Test Flexi Payslip March 2026',
                'employee_id': self.flexi_employee.id,
                'struct_id': self.structure.id,
                'version_id': self.flexi_employee.version_id.id,
                'date_from': date(2026, 3, 1),
                'date_to': date(2026, 3, 31),
            },
        ])
        payslips.compute_sheet()
        payslips.action_payslip_done()

        declaration_a = self.generate_flxwage_declaration(payslips[0])
        declaration_b = self.generate_flxwage_declaration(payslips[1])

        self.assertEqual(declaration_a.xml_filename, 'FI.FLEX.123456.20260415.00001.T.1.1')
        self.assertEqual(declaration_b.xml_filename, 'FI.FLEX.123456.20260415.00002.T.1.1')

        # I post my declaration, made a mistake and want to retry. num_suite should increment
        declaration_b.create_onss_declaration()
        declaration_b.generate_declaration_xml_report()
        self.assertEqual(declaration_b.xml_filename, 'FI.FLEX.123456.20260415.00003.T.1.1')

    @freeze_time('2026-04-15')
    def test_create_onss_declaration(self):
        payslip = self.create_slip(self.flexi_employee, date(2026, 1, 1), date(2026, 1, 31))
        declaration = self.generate_flxwage_declaration(payslip)

        self.assertEqual(declaration.state, 'ready')
        self.assertEqual(declaration.xml_filename, 'FI.FLEX.123456.20260415.00001.T.1.1')
        self.assertEqual(declaration.go_filename, 'GO.FLEX.123456.20260415.00001.T.1')

        onss_declaration = declaration.create_onss_declaration()

        self.assertEqual(onss_declaration.onss_file_count, 2)  # xml + go
        self.assertEqual(set(onss_declaration.onss_file_ids.mapped('name')), {'FI.FLEX.123456.20260415.00001.T.1.1', 'GO.FLEX.123456.20260415.00001.T.1'})

    def test_post_onss_declaration(self):
        payslip = self.create_slip(self.flexi_employee, date(2026, 1, 1), date(2026, 1, 31))
        declaration = self.generate_flxwage_declaration(payslip, skip_signature=False)
        onss_declaration = declaration.create_onss_declaration()

        with patch('odoo.addons.l10n_be_hr_payroll.models.l10n_be_onss_declaration.open_sftp_connection') as mock_open_conn:
            fake_sftp = MagicMock()
            mock_open_conn.return_value.__enter__.return_value = fake_sftp
            mock_open_conn.return_value.__exit__.return_value = None
            onss_declaration.action_post()
            mock_open_conn.assert_called_once()
            fake_sftp.putfo.assert_called()
        self.assertEqual(onss_declaration.state, 'posted')

    @freeze_time('2026-07-31')
    def test_declaration_flow_noti_anomaly(self):
        payslip = self.create_slip(self.flexi_employee, date(2026, 1, 1), date(2026, 1, 31))

        def make_file_mock(return_bytes):
            mock_file = MagicMock()
            mock_file.__enter__.return_value.read.return_value = return_bytes
            return mock_file

        declaration = self.generate_flxwage_declaration(payslip, skip_signature=False)
        onss_declaration_1 = declaration.create_onss_declaration()

        with patch('odoo.addons.l10n_be_hr_payroll.models.l10n_be_onss_declaration.open_sftp_connection') as mock_open_conn:
            fake_sftp = MagicMock()
            mock_open_conn.return_value.__enter__.return_value = fake_sftp
            mock_open_conn.return_value.__exit__.return_value = None
            onss_declaration_1.action_post()
        self.assertEqual(onss_declaration_1.state, 'posted')

        def mock_listdir_acrf_error(folder):
            if folder == 'OUT':
                return [
                    'FO.ACRF.999999.20260731.00124.S',
                    'FS.ACRF.999999.20260731.00124.S',
                    'GO.ACRF.999999.20260731.00124.S',
                ]
            return []

        def file_side_effect_acrf_error(remote_path, mode='rb'):
            if remote_path.endswith('FO.ACRF.999999.20260731.00124.S'):
                xml_str = """<?xml version="1.0" encoding="UTF-8"?>
<ACRF xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="ACRF_20262.xsd">
    <Form>
        <Identification>ACRF001</Identification>
        <FormCreationDate>2026-07-31</FormCreationDate>
        <FormCreationHour>11:31:06.661</FormCreationHour>
        <AttestationStatus>0</AttestationStatus>
        <TypeForm>FA</TypeForm>
        <FileReference>
            <FileName>%(xml_filename)s</FileName>
            <ReferenceOrigin>2</ReferenceOrigin>
            <ReferenceNbr>0380579WFBN6Z</ReferenceNbr>
        </FileReference>
        <ReceptionResult>
            <ResultCode>0</ResultCode>
            <ErrorID>ACRF-129</ErrorID>
        </ReceptionResult>
    </Form>
</ACRF>""" % {'xml_filename': declaration.xml_filename}
                return make_file_mock(xml_str.encode('utf-8'))
            if remote_path.endswith('FS.ACRF.999999.20260731.00124.S'):
                return make_file_mock(b"dummy\r\nsignature\r\n")
            if remote_path.endswith('GO.ACRF.999999.20260731.00124.S'):
                return make_file_mock(b"")
            raise FileNotFoundError(f"No mock for file: {remote_path}")

        with patch('odoo.addons.l10n_be_hr_payroll.models.l10n_be_onss_declaration.open_sftp_connection') as mock_open_conn:
            fake_sftp = MagicMock()
            fake_sftp.listdir.side_effect = mock_listdir_acrf_error
            fake_sftp.file.side_effect = file_side_effect_acrf_error
            mock_open_conn.return_value.__enter__.return_value = fake_sftp

            onss_declaration_1._fetch_files()

            assert fake_sftp.file.call_count == 3
            fake_sftp.file.assert_any_call('OUT/FO.ACRF.999999.20260731.00124.S', mode='rb')
            fake_sftp.file.assert_any_call('OUT/FS.ACRF.999999.20260731.00124.S', mode='rb')
            fake_sftp.file.assert_any_call('OUT/GO.ACRF.999999.20260731.00124.S', mode='rb')

        self.assertEqual(onss_declaration_1.state, 'error')
        self.assertEqual(onss_declaration_1.error_message, 'ACRF-129\nIncorrect file name prefix or Identification tag value in RFH2')

        with self.fake_time_object():
            declaration.generate_declaration_xml_report()
        onss_declaration_2 = declaration.create_onss_declaration()

        with patch('odoo.addons.l10n_be_hr_payroll.models.l10n_be_onss_declaration.open_sftp_connection') as mock_open_conn:
            fake_sftp = MagicMock()
            mock_open_conn.return_value.__enter__.return_value = fake_sftp
            mock_open_conn.return_value.__exit__.return_value = None
            onss_declaration_2.action_post()
        self.assertEqual(onss_declaration_2.state, 'posted')

        def mock_listdir_acrf_ok(folder):
            if folder == 'OUT':
                return [
                    'FO.ACRF.999999.20260731.00001.T',
                    'FS.ACRF.999999.20260731.00001.T',
                    'GO.ACRF.999999.20260731.00001.T',
                ]
            return []

        def file_side_effect_acrf_ok(remote_path, mode='rb'):
            if remote_path.endswith('FO.ACRF.999999.20260731.00001.T'):
                xml_str = """<?xml version="1.0" encoding="UTF-8"?>
<ACRF xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="ACRF_20262.xsd">
    <Form>
        <Identification>ACRF001</Identification>
        <FormCreationDate>2026-07-31</FormCreationDate>
        <FormCreationHour>11:40:34.220</FormCreationHour>
        <AttestationStatus>0</AttestationStatus>
        <TypeForm>FA</TypeForm>
        <FileReference>
            <FileName>%(go_filename)s</FileName>
            <ReferenceOrigin>2</ReferenceOrigin>
            <ReferenceNbr>0380579A83Q1Z</ReferenceNbr>
        </FileReference>
        <ReceptionResult>
            <ResultCode>1</ResultCode>
        </ReceptionResult>
    </Form>
</ACRF>""" % {'go_filename': declaration.go_filename}
                return make_file_mock(xml_str.encode('utf-8'))
            if remote_path.endswith('FS.ACRF.999999.20260731.00001.T'):
                return make_file_mock(b"dummy\r\nsignature\r\n")
            if remote_path.endswith('GO.ACRF.999999.20260731.00001.T'):
                return make_file_mock(b"")
            raise FileNotFoundError(f"No mock for file: {remote_path}")

        with patch('odoo.addons.l10n_be_hr_payroll.models.l10n_be_onss_declaration.open_sftp_connection') as mock_open_conn:
            fake_sftp = MagicMock()
            fake_sftp.listdir.side_effect = mock_listdir_acrf_ok
            fake_sftp.file.side_effect = file_side_effect_acrf_ok
            mock_open_conn.return_value.__enter__.return_value = fake_sftp

            onss_declaration_2._fetch_files()

            assert fake_sftp.file.call_count == 3
            fake_sftp.file.assert_any_call('OUT/FO.ACRF.999999.20260731.00001.T', mode='rb')
            fake_sftp.file.assert_any_call('OUT/FS.ACRF.999999.20260731.00001.T', mode='rb')
            fake_sftp.file.assert_any_call('OUT/GO.ACRF.999999.20260731.00001.T', mode='rb')

        self.assertEqual(onss_declaration_2.state, 'received')
        self.assertFalse(onss_declaration_2.error_message)

        # Receive Notification: valid (ResultCode 1) but flagging a non-blocking anomaly
        def mock_listdir_noti(folder):
            if folder in ('OUTTEST', 'OUTTEST-S'):
                return []
            elif folder == 'OUT':
                return [
                    'FO.NOTI.999999.20260731.00056.T',
                    'FS.NOTI.999999.20260731.00056.T',
                    'GO.NOTI.999999.20260731.00056.T',
                ]

        def file_side_effect_noti(remote_path, mode='rb'):
            flex_onss_file = onss_declaration_2.onss_file_ids.filtered(lambda f: f.declaration_type == 'FLEX' and f.file_type == 'FI')
            if remote_path.endswith('FO.NOTI.999999.20260731.00056.T'):
                xml_str = """<?xml version="1.0" encoding="UTF-8"?>
<NOTIFICATION xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
              xsi:noNamespaceSchemaLocation="NOTIFICATION_20243.xsd">
   <Form>
      <Identification>NOTI001</Identification>
      <FormCreationDate>2026-07-31</FormCreationDate>
      <FormCreationHour>11:40:39.945</FormCreationHour>
      <AttestationStatus>0</AttestationStatus>
      <TypeForm>FA</TypeForm>
      <HandledOriginalForm>
         <Identification>FLXWAGE</Identification>
         <FormCreationDate>%(form_creation_date)s</FormCreationDate>
         <FormCreationHour>%(form_creation_hour)s</FormCreationHour>
         <AttestationStatus>0</AttestationStatus>
         <TypeForm>SU</TypeForm>
      </HandledOriginalForm>
      <Reference>
         <ReferenceType>0</ReferenceType>
         <ReferenceOrigin>2</ReferenceOrigin>
         <ReferenceNbr>0380579A83Q1Z</ReferenceNbr>
      </Reference>
      <EmployerId>
         <NOSSRegistrationNbr>130387593</NOSSRegistrationNbr>
         <CompanyID>477472701</CompanyID>
      </EmployerId>
      <HandledReference>
         <ReferenceType>1</ReferenceType>
         <ReferenceOrigin>2</ReferenceOrigin>
         <ReferenceNbr>2BX002PAEVZAZ</ReferenceNbr>
      </HandledReference>
      <HandlingResult>
         <ResultCode>1</ResultCode>
         <AnomalyReport>
            <ErrorID>00024-152</ErrorID>
            <AnomalyClass>NB</AnomalyClass>
            <Path>
               <NOSSRegistrationNbr>130387593</NOSSRegistrationNbr>
               <CompanyID>477472701</CompanyID>
               <INSS>93051822361</INSS>
            </Path>
         </AnomalyReport>
      </HandlingResult>
   </Form>
</NOTIFICATION>
""" % {'form_creation_date': flex_onss_file.form_creation_date, 'form_creation_hour': flex_onss_file.form_creation_hour}
                return make_file_mock(xml_str.encode('utf-8'))
            if remote_path.endswith('FS.NOTI.999999.20260731.00056.T'):
                return make_file_mock(b"dummy\r\nsignature\r\n")
            if remote_path.endswith('GO.NOTI.999999.20260731.00056.T'):
                return make_file_mock(b"")
            raise FileNotFoundError(f"No mock for file: {remote_path}")

        with patch('odoo.addons.l10n_be_hr_payroll.models.l10n_be_onss_declaration.open_sftp_connection') as mock_open_conn:
            fake_sftp = MagicMock()
            fake_sftp.listdir.side_effect = mock_listdir_noti
            fake_sftp.file.side_effect = file_side_effect_noti
            mock_open_conn.return_value.__enter__.return_value = fake_sftp

            onss_declaration_2._fetch_files()

            assert fake_sftp.file.call_count == 3
            fake_sftp.file.assert_any_call('OUT/FO.NOTI.999999.20260731.00056.T', mode='rb')
            fake_sftp.file.assert_any_call('OUT/FS.NOTI.999999.20260731.00056.T', mode='rb')
            fake_sftp.file.assert_any_call('OUT/GO.NOTI.999999.20260731.00056.T', mode='rb')

        # Non-blocking anomaly: declaration is still notified as valid, but the anomaly is recorded
        self.assertEqual(onss_declaration_2.state, 'notified')
        self.assertEqual(
            onss_declaration_2.error_message,
            'Anomaly (1/1) - Code: 00024-152\nNo employment relationship found for the given period or date\n'
            '- Employee: Default Flexi Employee (NISS: 93051822361)\n- Anomaly Class: Non-blocking anomaly not rejecting the declaration\n\n')

    def test_performance(self):
        payslip = self.create_slip(self.flexi_employee, date(2026, 1, 1), date(2026, 1, 31))
        with self.assertQueryCount(50):
            declaration = self.env['l10n.be.flexi.at.work'].with_user(self.payroll_manager).create({
                'payslip_id': payslip.id,
                'environment': 'S',
            })
            with self.fake_time_object():
                declaration.with_context(onss_skip_signature=True).generate_declaration_xml_report()

    def test_performance_multi(self):
        employees = [
            self.create_flexi_employee({'name': f'Flexi Employee {i}'})
            for i in range(10)
        ]
        payslips = self.env['hr.payslip'].create([
            {
                'name': f'Flexi Payslip {i}',
                'employee_id': employees[i].id,
                'struct_id': self.structure.id,
                'version_id': employees[i].version_id.id,
                'date_from': date(2026, 1, 1),
                'date_to': date(2026, 1, 31),
            }
            for i in range(10)
        ])
        payslips.compute_sheet()
        payslips.action_payslip_done()
        with self.assertQueryCount(100):
            declarations = self.env['l10n.be.flexi.at.work'].with_user(self.payroll_manager).create([
                {'payslip_id': payslip.id, 'environment': 'T'}
                for payslip in payslips
            ])
            with self.fake_time_object():
                for declaration in declarations:
                    declaration.with_context(onss_skip_signature=True).generate_declaration_xml_report()
