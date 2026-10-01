# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from unittest.mock import patch
from dateutil.relativedelta import relativedelta

from odoo.addons.l10n_be_hr_payroll.models.hr_version import HrVersion
from odoo.exceptions import UserError
from odoo.tests.common import MockHTTPClient, TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'post_install_l10n', 'dimona')
@patch.object(HrVersion, '_dimona_authenticate', lambda version, company, declare=True: 'dummy-token')
@patch.object(HrVersion, '_cron_l10n_be_check_dimona', lambda version: True)
class TestDimona(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.belgium = cls.env.ref('base.be')

        cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').write({'active': True})
        cls.env.company.write({
            'country_id': cls.belgium.id,
            'onss_expeditor_number': '123456',
        })
        cls.env.company.payroll_config_ids[-1].write({
            'onss_registration_number': '125482497',
        })

        cls.employee = cls.env['hr.employee'].create({
            'name': 'Test Employee',
            'niss': '93051822361',
            'private_street': '23 Test Street',
            'private_city': 'Test City',
            'private_zip': '6800',
            'private_country_id': cls.belgium.id,
            'wage': 2000,
            'date_version': date.today() + relativedelta(day=1, months=1),
            'contract_date_start': date.today() + relativedelta(day=1, months=1),
            'sex': 'male',
        })

        cls.version = cls.employee.version_id

    def test_dimona_open_classic(self):
        wizard = self.env['l10n.be.dimona.wizard'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'declaration_type': 'in',
        })

        self.version.l10n_be_dimona_category = False  # as version default type is Employee, and it has default category we set it to False to test the error case of missing category
        with MockHTTPClient(return_headers={'Location': 'foo/bar/blork/2029409422'}, return_status=201):
            with self.assertRaises(UserError) as e:
                wizard.submit_declaration()
            self.assertIn('The DIMONA category is missing for employee', str(e.exception))

        self.version.l10n_be_dimona_category = 'oth'
        with MockHTTPClient(return_headers={'Location': 'foo/bar/blork/2029409422'}, return_status=201):
            wizard.submit_declaration()

        self.assertEqual(self.version.l10n_be_dimona_declaration_id.name, '2029409422')
        self.assertEqual(self.version.l10n_be_last_dimona_declaration_id.name, '2029409422')
        self.assertFalse(self.version.l10n_be_dimona_declaration_id.state)
        self.assertFalse(self.version.l10n_be_last_dimona_declaration_id.state)

    def test_dimona_open_foreigner(self):
        self.employee.write({
            'birthday': date(1991, 7, 28),
            'place_of_birth': 'Paris',
            'country_of_birth': self.env.ref('base.fr').id,
            'country_id': self.env.ref('base.fr').id,
            'sex': 'male',
        })

        wizard = self.env['l10n.be.dimona.wizard'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'declaration_type': 'in',
            'without_niss': True,
        })
        self.version.l10n_be_dimona_category = 'oth'

        with MockHTTPClient(return_headers={'Location': 'foo/bar/blork/2029409422'}, return_status=201):
            wizard.submit_declaration()

        self.assertEqual(self.version.l10n_be_dimona_declaration_id.name, '2029409422')
        self.assertEqual(self.version.l10n_be_last_dimona_declaration_id.name, '2029409422')
        self.assertFalse(self.version.l10n_be_dimona_declaration_id.state)
        self.assertFalse(self.version.l10n_be_last_dimona_declaration_id.state)

    def test_dimona_open_student(self):
        self.version.write({
            'l10n_be_dimona_category': 'stu',
            'l10n_be_dimona_planned_hours': 130,
            'date_end': date.today() + relativedelta(months=1, day=31),
        })
        wizard = self.env['l10n.be.dimona.wizard'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'declaration_type': 'in',
        })

        with MockHTTPClient(return_headers={'Location': 'foo/bar/blork/2029409422'}, return_status=201):
            wizard.submit_declaration()

        self.assertEqual(self.version.l10n_be_dimona_declaration_id.name, '2029409422')
        self.assertEqual(self.version.l10n_be_last_dimona_declaration_id.name, '2029409422')
        self.assertFalse(self.version.l10n_be_dimona_declaration_id.state)
        self.assertFalse(self.version.l10n_be_last_dimona_declaration_id.state)

    def test_dimona_close(self):
        self.version.l10n_be_dimona_declaration_id = self.env['l10n.be.dimona.declaration'].create({
                'name': '2029409422',
                'version_id': self.version.id,
                'employee_id': self.version.employee_id.id,
                'company_id': self.version.company_id.id,
            })
        self.version.contract_date_end = date.today() + relativedelta(months=1, day=31)

        wizard = self.env['l10n.be.dimona.wizard'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'declaration_type': 'out',
        })

        with MockHTTPClient(return_headers={'Location': 'foo/bar/blork/309320239'}, return_status=201):
            wizard.submit_declaration()

        self.assertEqual(self.version.l10n_be_dimona_declaration_id.name, '2029409422')
        self.assertEqual(self.version.l10n_be_last_dimona_declaration_id.name, '309320239')
        self.assertFalse(self.version.l10n_be_dimona_declaration_id.state)
        self.assertFalse(self.version.l10n_be_last_dimona_declaration_id.state)

    def test_dimona_update(self):
        self.version.l10n_be_dimona_declaration_id = self.env['l10n.be.dimona.declaration'].create({
                'name': '2029409422',
                'version_id': self.version.id,
                'employee_id': self.version.employee_id.id,
                'company_id': self.version.company_id.id,
            })
        self.version.contract_date_end = date.today() + relativedelta(months=1, day=31)
        self.version.l10n_be_dimona_category = 'oth'

        wizard = self.env['l10n.be.dimona.wizard'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'declaration_type': 'update',
        })

        with MockHTTPClient(return_headers={'Location': 'foo/bar/blork/309320239'}, return_status=201):
            wizard.submit_declaration()

        self.assertEqual(self.version.l10n_be_dimona_declaration_id.name, '2029409422')
        self.assertEqual(self.version.l10n_be_last_dimona_declaration_id.name, '309320239')
        self.assertFalse(self.version.l10n_be_dimona_declaration_id.state)
        self.assertFalse(self.version.l10n_be_last_dimona_declaration_id.state)

    def test_dimona_cancel(self):
        self.version.l10n_be_dimona_declaration_id = self.env['l10n.be.dimona.declaration'].create({
                'name': '2029409422',
                'version_id': self.version.id,
                'employee_id': self.version.employee_id.id,
                'company_id': self.version.company_id.id,
            })

        wizard = self.env['l10n.be.dimona.wizard'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'declaration_type': 'cancel',
        })

        with MockHTTPClient(return_headers={'Location': 'foo/bar/blork/309320239'}, return_status=201):
            wizard.submit_declaration()

        self.assertEqual(self.version.l10n_be_dimona_declaration_id.name, '2029409422')
        self.assertEqual(self.version.l10n_be_last_dimona_declaration_id.name, '309320239')
        self.assertFalse(self.version.l10n_be_dimona_declaration_id.state)
        self.assertFalse(self.version.l10n_be_last_dimona_declaration_id.state)

    def test_dimona_flow_classic(self):
        # pylint: disable=function-redefined
        certificate = self.env['certificate.certificate'].create({'name': 'onss cert'})
        self.version.date_version = date(2025, 9, 26)
        self.version.contract_date_start = date(2025, 9, 26)

        self.env.company.write({
            'onss_certificate_id': certificate,
        })

        # No dimona yet
        self.assertFalse(self.employee.l10n_be_dimona_declaration_id)
        self.assertFalse(self.employee.l10n_be_last_dimona_declaration_id)

        # Needs Dimona IN is true
        self.assertTrue(self.employee.l10n_be_needs_dimona_in)
        self.assertFalse(self.employee.l10n_be_needs_dimona_update)
        self.assertFalse(self.employee.l10n_be_needs_dimona_out)
        self.assertFalse(self.employee.l10n_be_needs_dimona_cancel)
        self.assertEqual(self.employee.l10n_be_dimona_next_action, 'in')

        self.version.l10n_be_dimona_category = False  # as version default type is Employee, and it has default category we set it to False to test the error case of missing category
        with MockHTTPClient(return_headers={'Location': 'foo/bar/blork/2029409422'}, return_status=201):
            with self.assertRaises(UserError) as e:
                self.employee.action_send_dimona()
            self.assertIn('The DIMONA category is missing for employee', str(e.exception))

        self.version.l10n_be_dimona_category = 'oth'
        with MockHTTPClient(return_headers={'Location': 'foo/bar/blork/2029409422'}, return_status=201):
            self.employee.action_send_dimona()

        # Dimona IN created
        self.assertEqual(self.version.l10n_be_dimona_declaration_id.name, '2029409422')
        self.assertEqual(self.version.l10n_be_last_dimona_declaration_id.name, '2029409422')
        self.assertFalse(self.version.l10n_be_dimona_declaration_id.state)
        self.assertFalse(self.version.l10n_be_last_dimona_declaration_id.state)

        # No displayed button, nothing to do
        self.assertFalse(self.employee.l10n_be_needs_dimona_in)
        self.assertFalse(self.employee.l10n_be_needs_dimona_update)
        self.assertFalse(self.employee.l10n_be_needs_dimona_out)
        self.assertFalse(self.employee.l10n_be_needs_dimona_cancel)
        self.assertEqual(self.employee.l10n_be_dimona_next_action, 'progress')

        with MockHTTPClient(return_json={
            "href": "https://services-sim.socialsecurity.be/REST/dimona/v2/declarations/2029409422", "worker": {"ssin": "93051822361", "gender": "1", "birthDate": "1991-11-11", "givenName": "TEST", "familyName": "EMPLOYEE", "givenNames": "TEST EMPLOYEE", "nationality": 150}, "dimonaIn": {"features": {"workerType": "OTH", "jointCommissionNumber": "XXX"}, "startDate": "2025-09-26"}, "employer": {"employerId": 12548245, "enterpriseNumber": "477472701"}, "declarationStatus": {"period": {"id": 2029409422, "href": "https://services-sim.socialsecurity.be/REST/dimona/v2/periods/2029409422"}, "result": "B", "declarationId": 2029409422}
        }, return_status=200):
            self.employee.action_check_dimona()

        self.assertEqual(self.version.l10n_be_dimona_declaration_id.state, 'B')
        self.assertEqual(self.version.l10n_be_last_dimona_declaration_id.state, 'B')

        # Dimona issue, send dimona button is displayed to resubmit dimona in
        self.assertTrue(self.employee.l10n_be_needs_dimona_in)
        self.assertFalse(self.employee.l10n_be_needs_dimona_update)
        self.assertFalse(self.employee.l10n_be_needs_dimona_out)
        self.assertFalse(self.employee.l10n_be_needs_dimona_cancel)
        self.assertEqual(self.employee.l10n_be_dimona_next_action, 'issue')

        with MockHTTPClient(return_json={
            "href": "https://services-sim.socialsecurity.be/REST/dimona/v2/declarations/2029409411", "worker": {"ssin": "93051822361", "gender": "1", "birthDate": "1991-11-11", "givenName": "TEST", "familyName": "EMPLOYEE", "givenNames": "TEST EMPLOYEE", "nationality": 150}, "dimonaIn": {"features": {"workerType": "OTH", "jointCommissionNumber": "XXX"}, "startDate": "2025-09-26"}, "employer": {"employerId": 125482497, "enterpriseNumber": "477472701"}, "declarationStatus": {"period": {"id": 2029409422, "href": "https://services-sim.socialsecurity.be/REST/dimona/v2/periods/2029409422"}, "result": "A", "declarationId": 2029409411}
        }, return_status=200):
            self.employee.action_check_dimona()

        self.assertEqual(self.version.l10n_be_dimona_declaration_id.state, 'A')
        self.assertEqual(self.version.l10n_be_last_dimona_declaration_id.state, 'A')

        # No displayed button, nothing to do
        self.assertFalse(self.employee.l10n_be_needs_dimona_in)
        self.assertFalse(self.employee.l10n_be_needs_dimona_update)
        self.assertFalse(self.employee.l10n_be_needs_dimona_out)
        self.assertFalse(self.employee.l10n_be_needs_dimona_cancel)
        self.assertEqual(self.employee.l10n_be_dimona_next_action, 'done')

        # unset the certificate to avoid automatic declaration on write
        self.env.company.write({
            'onss_certificate_id': False,
        })

        # Now, update contract start date
        self.version.date_version = date(2025, 7, 3)
        self.version.contract_date_start = date(2025, 7, 3)

        self.env.company.write({
            'onss_certificate_id': certificate,
        })

        # send dimona button is displayed for dimona update
        self.assertFalse(self.employee.l10n_be_needs_dimona_in)
        self.assertTrue(self.employee.l10n_be_needs_dimona_update)
        self.assertFalse(self.employee.l10n_be_needs_dimona_out)
        self.assertFalse(self.employee.l10n_be_needs_dimona_cancel)
        self.assertEqual(self.employee.l10n_be_dimona_next_action, 'update')

        with MockHTTPClient(return_headers={'Location': 'foo/bar/blork/656309296521'}, return_status=201):
            self.employee.action_send_dimona()

        # No displayed button, waiting for status
        self.assertFalse(self.employee.l10n_be_needs_dimona_in)
        self.assertTrue(self.employee.l10n_be_needs_dimona_update)
        self.assertFalse(self.employee.l10n_be_needs_dimona_out)
        self.assertFalse(self.employee.l10n_be_needs_dimona_cancel)
        self.assertEqual(self.employee.l10n_be_dimona_next_action, 'progress')

        self.assertEqual(self.version.l10n_be_dimona_declaration_id.name, '2029409422')
        self.assertEqual(self.version.l10n_be_last_dimona_declaration_id.name, '656309296521')
        self.assertFalse(self.version.l10n_be_last_dimona_declaration_id.state)

        with MockHTTPClient(return_json={
            "href": "https://services-sim.socialsecurity.be/REST/dimona/v2/declarations/656309296521", "worker": {"ssin": "93051822361", "gender": "1", "birthDate": "1991-11-11", "givenName": "TEST", "familyName": "EMPLOYEE", "givenNames": "TEST EMPLOYEE", "nationality": 150}, "employer": {"employerId": 125482497, "enterpriseNumber": "477472701"}, "dimonaUpdate": {"periodId": 656309292174, "startDate": "2025-07-03"}, "declarationStatus": {"period": {"id": 656309292174, "href": "https://services-sim.socialsecurity.be/REST/dimona/v2/periods/656309292174"}, "result": "B", "declarationId": 656309296521}
        }, return_status=200):
            self.employee.action_check_dimona()

        self.assertEqual(self.version.l10n_be_dimona_declaration_id.state, 'A')
        self.assertEqual(self.version.l10n_be_last_dimona_declaration_id.state, 'B')

        # No displayed button, nothing to do
        self.assertFalse(self.employee.l10n_be_needs_dimona_in)
        self.assertTrue(self.employee.l10n_be_needs_dimona_update)
        self.assertFalse(self.employee.l10n_be_needs_dimona_out)
        self.assertFalse(self.employee.l10n_be_needs_dimona_cancel)
        self.assertEqual(self.employee.l10n_be_dimona_next_action, 'issue')

        with MockHTTPClient(
            return_json={
                "href": "https://services-sim.socialsecurity.be/REST/dimona/v2/declarations/656309296531", "worker": {"ssin": "93051822361", "gender": "1", "birthDate": "1991-11-11", "givenName": "TEST", "familyName": "EMPLOYEE", "givenNames": "TEST EMPLOYEE", "nationality": 150}, "employer": {"employerId": 125482497, "enterpriseNumber": "477472701"}, "dimonaUpdate": {"periodId": 656309292174, "startDate": "2025-07-03"}, "declarationStatus": {"period": {"id": 656309292174, "href": "https://services-sim.socialsecurity.be/REST/dimona/v2/periods/656309292174"}, "result": "A", "declarationId": 656309296531}
            },
            return_status=200,
        ):
            self.employee.action_check_dimona()

        self.assertEqual(self.version.l10n_be_last_dimona_declaration_id.state, 'A')

        # No displayed button, nothing to do
        self.assertFalse(self.employee.l10n_be_needs_dimona_in)
        self.assertFalse(self.employee.l10n_be_needs_dimona_update)
        self.assertFalse(self.employee.l10n_be_needs_dimona_out)
        self.assertFalse(self.employee.l10n_be_needs_dimona_cancel)
        self.assertEqual(self.employee.l10n_be_dimona_next_action, 'done')

        # unset the certificate to avoid automatic declaration on write
        self.env.company.write({
            'onss_certificate_id': False,
        })

        departure_reason = self.env['hr.departure.reason'].create({
            'name': 'End of Contract',
        })
        self.employee.departure_reason_id = departure_reason.id

        worker_code_495 = self.env['l10n.be.worker.code'].create({
            'name': 'Student/Trainee',
            'dmfa_code': '495',
            'egov3_code': '00495',
        })
        self.version.l10n_be_worker_code_id = worker_code_495.id

        # Now, set contract end date
        self.version.contract_date_end = date(2025, 9, 24)

        self.env.company.write({
            'onss_certificate_id': certificate,
        })

        # send dimona button is displayed for dimona out
        self.assertFalse(self.employee.l10n_be_needs_dimona_in)
        self.assertFalse(self.employee.l10n_be_needs_dimona_update)
        self.assertTrue(self.employee.l10n_be_needs_dimona_out)
        self.assertFalse(self.employee.l10n_be_needs_dimona_cancel)
        self.assertEqual(self.employee.l10n_be_dimona_next_action, 'out')

        with MockHTTPClient(return_headers={'Location': 'foo/bar/blork/656309314911'}, return_status=201):
            self.employee.action_send_dimona()

        # No displayed button, waiting for status
        self.assertFalse(self.employee.l10n_be_needs_dimona_in)
        self.assertFalse(self.employee.l10n_be_needs_dimona_update)
        self.assertTrue(self.employee.l10n_be_needs_dimona_out)
        self.assertFalse(self.employee.l10n_be_needs_dimona_cancel)
        self.assertEqual(self.employee.l10n_be_dimona_next_action, 'progress')

        self.assertEqual(self.version.l10n_be_dimona_declaration_id.name, '2029409422')
        self.assertEqual(self.version.l10n_be_last_dimona_declaration_id.name, '656309314911')
        self.assertFalse(self.version.l10n_be_last_dimona_declaration_id.state)

        with MockHTTPClient(
            return_json={
                "href": "https://services-sim.socialsecurity.be/REST/dimona/v2/declarations/656309314911", "worker": {"ssin": "93051822361", "gender": "1", "birthDate": "1991-11-11", "givenName": "TEST", "familyName": "EMPLOYEE", "givenNames": "TEST EMPLOYEE", "nationality": 150}, "employer": {"employerId": 125482497, "enterpriseNumber": "477472701"}, "dimonaOut": {"endDate": "2025-09-24", "periodId": 656309292174}, "declarationStatus": {"period": {"id": 656309292174, "href": "https://services-sim.socialsecurity.be/REST/dimona/v2/periods/656309292174"}, "result": "A", "declarationId": 656309314911}
            },
            return_status=200,
        ):
            self.employee.action_check_dimona()

        self.assertEqual(self.version.l10n_be_last_dimona_declaration_id.state, 'A')

        # No displayed button, nothing to do
        self.assertFalse(self.employee.l10n_be_needs_dimona_in)
        self.assertFalse(self.employee.l10n_be_needs_dimona_update)
        self.assertFalse(self.employee.l10n_be_needs_dimona_out)
        self.assertFalse(self.employee.l10n_be_needs_dimona_cancel)
        self.assertEqual(self.employee.l10n_be_dimona_next_action, 'done')

        # unset the certificate to avoid automatic declaration on write
        self.env.company.write({
            'onss_certificate_id': False,
        })

        # Last, archive employee because contract was cancelled
        self.employee.active = False

        self.env.company.write({
            'onss_certificate_id': certificate,
        })

        # send dimona button is displayed for dimona cancel
        self.assertFalse(self.employee.l10n_be_needs_dimona_in)
        self.assertFalse(self.employee.l10n_be_needs_dimona_update)
        self.assertFalse(self.employee.l10n_be_needs_dimona_out)
        self.assertTrue(self.employee.l10n_be_needs_dimona_cancel)
        self.assertEqual(self.employee.l10n_be_dimona_next_action, 'cancel')

        with MockHTTPClient(return_headers={'Location': 'foo/bar/blork/656309322385'}, return_status=201):
            self.employee.action_send_dimona()

        # No displayed button, waiting for status
        self.assertFalse(self.employee.l10n_be_needs_dimona_in)
        self.assertFalse(self.employee.l10n_be_needs_dimona_update)
        self.assertFalse(self.employee.l10n_be_needs_dimona_out)
        self.assertTrue(self.employee.l10n_be_needs_dimona_cancel)
        self.assertEqual(self.employee.l10n_be_dimona_next_action, 'progress')

        self.assertEqual(self.version.l10n_be_dimona_declaration_id.name, '2029409422')
        self.assertEqual(self.version.l10n_be_last_dimona_declaration_id.name, '656309322385')
        self.assertFalse(self.version.l10n_be_last_dimona_declaration_id.state)

        with MockHTTPClient(
            return_json={
                "worker": {"ssin": "93051822361", "gender": "1", "birthDate": "1991-11-11", "givenName": "TEST", "familyName": "EMPLOYEE", "givenNames": "TEST EMPLOYEE", "nationality": 150}, "employer": {"employerId": 125482497, "enterpriseNumber": "477472701"}, "dimonaCancel": {"periodId": 656309292174}, "declarationStatus": {"period": {"id": 656309292174, "href": "https://services-sim.socialsecurity.be/REST/dimona/v2/periods/656309292174"}, "result": "A", "declarationId": 656309322385}
            },
            return_status=200,
        ):
            self.employee.action_check_dimona()

        self.assertEqual(self.version.l10n_be_last_dimona_declaration_id.state, 'A')

        # No displayed button, nothing to do
        self.assertFalse(self.employee.l10n_be_needs_dimona_in)
        self.assertFalse(self.employee.l10n_be_needs_dimona_update)
        self.assertFalse(self.employee.l10n_be_needs_dimona_out)
        self.assertFalse(self.employee.l10n_be_needs_dimona_cancel)
        self.assertEqual(self.employee.l10n_be_dimona_next_action, 'done')

    def test_dimona_periods_alignment_mismatch_warning(self):
        certificate = self.env["certificate.certificate"].create({"name": "onss cert"})
        self.version.date_version = date(2025, 9, 26)
        self.version.contract_date_start = date(2025, 9, 26)
        self.version.l10n_be_dimona_category = "oth"

        self.version.company_id.write({"onss_certificate_id": certificate})

        period_id = "2029409422"
        declaration_id = 2029409422
        with MockHTTPClient(
            return_json={
                "items": [
                    {
                        "worker": {
                            "ssin": self.employee.niss,
                            "gender": "1",
                            "birthDate": "1991-11-11",
                            "givenName": "TEST",
                            "familyName": "EMPLOYEE",
                            "givenNames": "TEST EMPLOYEE",
                            "nationality": 150,
                        },
                        "startDate": "2025-09-26",
                        "endDate": "2025-10-25",
                        "periodId": period_id,
                        "dimonaIn": {
                            "features": {
                                "workerType": "STU",
                                "jointCommissionNumber": "100",
                            },
                            "startDate": "2025-09-26",
                        },
                        "employer": {
                            "employerId": 12548245,
                            "enterpriseNumber": "477472701",
                        },
                        "declarationStatus": {
                            "period": {
                                "id": declaration_id,
                            },
                            "result": "A",
                            "declarationId": declaration_id,
                        },
                    }
                ],
                "next": False,
            },
            return_status=200,
        ):
            self.version.action_fetch_all_dimona()

        relation = self.env["l10n.be.dimona.relation"].search([("name", "=", self.employee.niss)])

        self.assertEqual(relation.employee_id, self.employee)
        issues = self.version.issues or {}
        self.assertIn("Dimona periods and contract versions are not aligned", " ".join(issue["message"] for issue in issues.values()))

    def test_dimona_periods_category_mismatch_warning(self):
        certificate = self.env["certificate.certificate"].create({"name": "onss cert"})
        self.version.date_version = date(2025, 9, 26)
        self.version.contract_date_start = date(2025, 9, 26)
        self.version.contract_date_end = date(2025, 10, 25)
        self.version.l10n_be_dimona_category = "oth"
        self.version.l10n_be_joint_committee_id = self.env.ref("l10n_be_hr_payroll.l10n_be_joint_committee_302").id

        self.version.company_id.write({"onss_certificate_id": certificate})

        period_id = "2029409422"
        declaration_id = 2029409422
        with MockHTTPClient(
            return_json={
                "items": [
                    {
                        "worker": {
                            "ssin": self.employee.niss,
                            "gender": "1",
                            "birthDate": "1991-11-11",
                            "givenName": "TEST",
                            "familyName": "EMPLOYEE",
                            "givenNames": "TEST EMPLOYEE",
                            "nationality": 150,
                        },
                        "startDate": "2025-09-26",
                        "endDate": "2025-10-25",
                        "periodId": period_id,
                        "dimonaIn": {
                            "features": {
                                "workerType": "STU",
                                "jointCommissionNumber": "100",
                            },
                            "startDate": "2025-09-26",
                        },
                        "employer": {
                            "employerId": 12548245,
                            "enterpriseNumber": "477472701",
                        },
                        "declarationStatus": {
                            "period": {
                                "id": declaration_id,
                            },
                            "result": "A",
                            "declarationId": declaration_id,
                        },
                    }
                ],
                "next": False,
            },
            return_status=200,
        ):
            self.version.action_fetch_all_dimona()

        relation = self.env["l10n.be.dimona.relation"].search([("name", "=", self.employee.niss)])

        self.assertEqual(relation.employee_id, self.employee)
        issues = self.version.issues or {}
        self.assertIn("The Dimona category does not match the contract version one", " ".join(issue["message"] for issue in issues.values()))
        self.assertIn("The Dimona joint committee does not match the contract version one", " ".join(issue["message"] for issue in issues.values()))

    def test_dimona_needs_in_survives_stale_explicit_create_vals(self):
        # l10n_be_needs_dimona_in must stay purely server-computed.
        # The web client treats it as editable because of readonly=False, even though no view renders it as a widget, only button invisible= domains reference it.
        # An early onchange can compute it False before contract_date_start is filled in, and autosave then submits that stale value explicitly.
        # The ORM must not let an explicit vals value suppress the recompute here.
        employee = self.env['hr.employee'].create({
            'name': 'Test Employee Stale Vals',
            'niss': '93051822460',
            'private_country_id': self.belgium.id,
            'wage': 2000,
            'date_version': date.today() + relativedelta(day=1, months=1),
            'contract_date_start': date.today() + relativedelta(day=1, months=1),
            'sex': 'male',
            'l10n_be_needs_dimona_in': False,
        })

        self.assertTrue(employee.l10n_be_needs_dimona_in)
        self.assertEqual(employee.l10n_be_dimona_next_action, 'in')
