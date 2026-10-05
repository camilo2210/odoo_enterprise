# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime
from unittest.mock import MagicMock, patch

from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon
from odoo.addons.l10n_be_hr_payroll.models.certificate import CertificateCertificate
from odoo.addons.l10n_be_hr_payroll.models.utils import xml_str_to_dict
from odoo.addons.l10n_be_hr_payroll.tests.common import TestBelgiumCommon
from odoo.tests import freeze_time, tagged


@tagged('post_install', '-at_install', 'drs')
@patch.object(CertificateCertificate, '_decode_certificate_for_be_onss_xml', lambda contract, xml_str: b'dummy\r\nsignature\r\n')
class TestDRS(TestPayslipValidationCommon, TestBelgiumCommon):

    @classmethod
    @TestPayslipValidationCommon.setup_country('be')
    def setUpClass(cls):
        super().setUpClass()

        cls.belgian_company = cls.company_data['company']

        cls.belgian_company.write({
            'vat': 'BE0897223670',
            'phone': '0471098765',
            'street': 'Test street',
            'city': 'Test city',
            'zip': '8292',
            'onss_expeditor_number': '123456',
            'country_id': cls.env.ref('base.be').id,
        })
        cls.belgian_company.current_payroll_config_id.write({
            'l10n_be_company_number': '0123456749',
            'l10n_be_revenue_code': '1234',
            'onss_registration_number': '125482497',
            'onss_importance_code': '4',
            'l10n_be_employer_category_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_employer_category_00010').id,
        })

        cls.calendar_38h = cls.env['resource.calendar'].create({
            'name': 'Standard 38 hours/week',
            'company_id': cls.belgian_company.id,
            'hours_per_day': 7.6,
            'attendance_ids': [(5, 0, 0),
                (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '0', 'hour_from': 13, 'hour_to': 16.6}),
                (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '1', 'hour_from': 13, 'hour_to': 16.6}),
                (0, 0, {'dayofweek': '2', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '2', 'hour_from': 13, 'hour_to': 16.6}),
                (0, 0, {'dayofweek': '3', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '3', 'hour_from': 13, 'hour_to': 16.6}),
                (0, 0, {'dayofweek': '4', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '4', 'hour_from': 13, 'hour_to': 16.6})
            ],
        })

        # Youth: age at Dec 31, 2025 = 22 (< 25 → youth risk, code 001)
        # Senior: age at Dec 31, 2025 = 60 (>= 50 → senior risk, code 002)
        cp_200 = cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200')
        cls.employee_youth, cls.employee_senior = cls.env['hr.employee'].create([
            {
                'name': 'Youth Worker',
                'company_id': cls.belgian_company.id,
                'birthday': date(2003, 6, 1),
                'contract_date_start': date(2025, 1, 1),
                'date_version': date(2025, 1, 1),
                'resource_calendar_id': cls.calendar_38h.id,
                'niss': '/',
                'lang': 'fr_BE',
                'l10n_be_joint_committee_id': cp_200.id,
            },
            {
                'name': 'Senior Worker',
                'company_id': cls.belgian_company.id,
                'birthday': date(1965, 6, 1),
                'contract_date_start': date(2025, 1, 1),
                'date_version': date(2025, 1, 1),
                'resource_calendar_id': cls.calendar_38h.id,
                'niss': '/',
                'lang': 'nl_NL',
                'l10n_be_joint_committee_id': cp_200.id,
            },
        ])

    def _set_create_date(self, records, new_date):
        # The ORM discards create_date from create()/write() vals, so it must be forced through SQL update + cache invalidation
        self.env.cr.execute(
            f"UPDATE {records._table} SET create_date = %s WHERE id IN %s",
            (new_date, tuple(records.ids)),
        )
        records.invalidate_recordset(['create_date'])
        records._compute_name()

    def _get_drs_dict(self, drs, skip_signature=True):
        drs.with_context(onss_skip_signature=skip_signature).generate_declaration_xml_report()
        self.assertFalse(drs.error_message)
        self.assertEqual(drs.state, 'ready')
        return xml_str_to_dict(drs.xml_file.content)

    @freeze_time('2026-06-26 10:00:00')
    def test_wech009_wech010_automation(self):
        youth_time_off_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_youth_time_off')
        allocation_youth, allocation_senior = self.env['hr.leave.allocation'].create([
            {
                'employee_id': self.employee_youth.id,
                'work_entry_type_id': youth_time_off_type.id,
                'number_of_days': 20,
                'date_from': date(2025, 1, 1),
            },
            {
                'employee_id': self.employee_senior.id,
                'work_entry_type_id': youth_time_off_type.id,
                'number_of_days': 20,
                'date_from': date(2025, 1, 1),
            },
        ])
        (allocation_youth + allocation_senior).action_approve()
        # Validating a youth time off allocation for an employee under 25 creates a WECH009 (code 001)
        wech009_youth = allocation_youth.linked_drs_ids
        wech009_youth.write({'environment': 'T'})
        # force the value of create_date to ensure expected date/name values in the declaration file
        self._set_create_date(wech009_youth, datetime(2026, 6, 26, 10, 0, 0))
        self.assertEqual(len(wech009_youth), 1)
        self.assertEqual(wech009_youth.identification, 'WECH009')
        self.assertEqual(wech009_youth.code, '001')
        # Validating a youth time off allocation for an employee under 25 creates a WECH009 (code 001)
        wech009_senior = allocation_senior.linked_drs_ids
        wech009_senior.write({'environment': 'T'})
        self._set_create_date(wech009_senior, datetime(2026, 6, 26, 10, 0, 0))
        self.assertEqual(len(wech009_senior), 1)
        self.assertEqual(wech009_senior.identification, 'WECH009')
        self.assertEqual(wech009_senior.code, '002')

        self.env['hr.leave'].create([
            {
                'employee_id': self.employee_youth.id,
                'work_entry_type_id': youth_time_off_type.id,
                'request_date_from': date(2025, 3, 10),
                'request_date_to': date(2025, 3, 12),
            },
            {
                'employee_id': self.employee_senior.id,
                'work_entry_type_id': youth_time_off_type.id,
                'request_date_from': date(2025, 3, 10),
                'request_date_to': date(2025, 3, 12),
            },
        ])
        wech010_per_emp = dict(self.env['l10n.be.drs']._read_group([
            ('employee_id', 'in', (self.employee_youth + self.employee_senior).ids),
            ('identification', '=', 'WECH010'),
        ], groupby=['employee_id'], aggregates=['id:recordset']))
        wech010_youth = wech010_per_emp.get(self.employee_youth)
        self.assertEqual(len(wech010_youth), 1)
        self.assertEqual(wech010_youth.code, '001')
        wech010_senior = wech010_per_emp.get(self.employee_senior)
        self.assertEqual(len(wech010_senior), 1)
        self.assertEqual(wech010_senior.code, '002')

        # Check wech009_youth validity
        wech009_youth.environment = 'T'
        self.belgian_company.onss_certificate_id = self.env['certificate.certificate'].create({})
        wech009_youth_dict = self._get_drs_dict(wech009_youth, skip_signature=False)
        self.cr.flush()
        self.assertDictEqual(wech009_youth_dict, {'WECH009': {'@{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation': 'drs/WECH009_20261.xsd', 'Form': {'Identification': 'WECH009', 'FormCreationDate': '2026-06-26', 'FormCreationHour': '10:00:00.000', 'AttestationStatus': '0', 'TypeForm': 'SU', 'DclInformation': {'LanguageCodePdf': '2'}, 'RiskIdentification': {'IdentificationOfRisk': '001'}, 'Reference': {'ReferenceType': '1', 'ReferenceOrigin': '1', 'ReferenceNbr': '20260626100000000000'}, 'EmployerDeclarationLink': {'NOSSRegistrationNbr': '125482497', 'Trusteeship': '0', 'CompanyID': '0123456749', 'NaturalPerson': {'NaturalPersonSequenceNbr': '1', 'INSS': '00000000000', 'WorkerRecordLink': {'EmployerClass': '010', 'WorkerCode': '495', 'OccupationLink': {'OccupationStartingDate': '2025-01-01', 'JointCommissionNbr': '200', 'WorkingDaysSystem': '500', 'MeanWorkingHours': '3800', 'RefMeanWorkingHours': '3800', 'AnnualDclYoungHolidays': {'MonthOfYoungAnnualHolidays': '2026-06', 'CalculationBaseAllowance': {'RemunerationTimeUnit': '4', 'RemunerationBasisAmount': '0'}, 'HolidaysSector': {'HolidaySectorIndicator': '1', 'HoursHolidayDetail': {'HolidayCode': '7', 'HolidayHoursNumber': '15200'}}}}}}}}}})

        wech009_youth.create_onss_declaration()
        declaration = wech009_youth.onss_declaration_ids
        self.assertEqual(len(declaration), 1)
        self.assertEqual(declaration.onss_file_count, 3)

        with patch('odoo.addons.l10n_be_hr_payroll.models.l10n_be_onss_declaration.open_sftp_connection') as mock_open_conn:
            fake_sftp = MagicMock()
            fake_sftp.putfo = MagicMock()
            # This mock needs to simulate the context manager behavior, specifically the __enter__ and __exit__ methods
            mock_open_conn.return_value.__enter__.return_value = fake_sftp
            mock_open_conn.return_value.__exit__.return_value = None
            declaration.action_post()
            mock_open_conn.assert_called_once()
            fake_sftp.putfo.assert_called()

        self.assertEqual(declaration.state, 'posted')

        # Receive ACRF, signaling an invalid signature
        def mock_listdir_declaration_1(folder):
            if folder in ('OUT', 'OUTTEST-S'):
                return []
            elif folder == 'OUTTEST':
                return [
                    'FO.ACRF.999999.20250410.99999.T',
                    'FS.ACRF.999999.20250410.99999.T',
                    'GO.ACRF.999999.20250410.99999.T',
                ]

        def make_file_mock(return_bytes):
            mock_file = MagicMock()
            mock_file.__enter__.return_value.read.return_value = return_bytes
            return mock_file

        def file_side_effect_declaration_1(remote_path, mode='rb'):
            if remote_path.endswith('FO.ACRF.999999.20250410.99999.T'):
                xml_str = f"""<?xml version="1.0" encoding="UTF-8"?>
<ACRF xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="ACRF_20262.xsd">
	<Form>
		<Identification>ACRF001</Identification>
		<FormCreationDate>2026-01-16</FormCreationDate>
		<FormCreationHour>15:29:46.495</FormCreationHour>
		<AttestationStatus>0</AttestationStatus>
		<TypeForm>PA</TypeForm>
		<FileReference>
			<FileName>{wech009_youth.go_filename}</FileName>
			<ReferenceOrigin>2</ReferenceOrigin>
			<ReferenceNbr>3400001Y1P01G</ReferenceNbr>
		</FileReference>
		<ReceptionResult>
			<ResultCode>0</ResultCode>
			<ErrorID>ACRF-088</ErrorID>
			<ErrorID>ACRF-172</ErrorID>
		</ReceptionResult>
	</Form>
</ACRF>"""
                return make_file_mock(xml_str.encode('utf-8'))
            if remote_path.endswith('FS.ACRF.999999.20250410.99999.T'):
                return make_file_mock(b"dummy\r\nsignature\r\n")
            if remote_path.endswith('GO.ACRF.999999.20250410.99999.T'):
                return make_file_mock(b"")
            raise FileNotFoundError(f"No mock for file: {remote_path}")

        with patch('odoo.addons.l10n_be_hr_payroll.models.l10n_be_onss_declaration.open_sftp_connection') as mock_open_conn:
            fake_sftp = MagicMock()
            fake_sftp.listdir.side_effect = mock_listdir_declaration_1
            fake_sftp.file.side_effect = file_side_effect_declaration_1

            mock_open_conn.return_value.__enter__.return_value = fake_sftp

            declaration._fetch_files()

            assert fake_sftp.file.call_count == 3
            fake_sftp.file.assert_any_call('OUTTEST/FO.ACRF.999999.20250410.99999.T', mode='rb')
            fake_sftp.file.assert_any_call('OUTTEST/FS.ACRF.999999.20250410.99999.T', mode='rb')
            fake_sftp.file.assert_any_call('OUTTEST/GO.ACRF.999999.20250410.99999.T', mode='rb')

        self.assertEqual(declaration.state, 'error')
        self.assertEqual(declaration.onss_file_count, 6)
