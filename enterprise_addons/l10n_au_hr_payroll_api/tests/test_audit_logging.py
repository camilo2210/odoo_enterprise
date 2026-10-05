# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import date

from odoo import Command
from odoo.tests import tagged, Form, new_test_user
from .common import TestL10nAUPayrollAPICommon


@tagged("post_install_l10n", "post_install", "-at_install", "l10n_au_hr_payroll")
class TestAuditLogging(TestL10nAUPayrollAPICommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create({
            "name": "Australian Company ( test )",
            "country_id": cls.env.ref("base.au").id,
            "currency_id": cls.env.ref("base.AUD").id,
            "l10n_au_registered_for_whm": True,
            "l10n_au_registered_for_palm": True,
            "vat": "85658499097",
        })
        cls.resource_calendar = cls.company.resource_calendar_id
        cls.env.user.company_ids |= cls.company
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.company.ids))
        cls.proxy_user = cls.env['account_edi_proxy_client.user']._register_proxy_user(cls.company, 'l10n_au_payroll', 'demo')
        cls.proxy_user.edi_mode = 'test'

        cls.env.user.tz = 'Australia/Sydney'

        cls.resource_calendar_40_hours_per_week = cls.env['resource.calendar'].create([{
            'name': "Test Calendar : 38 Hours/Week",
            'company_id': cls.env.company.id,
            'hours_per_day': 7.6,
            'hours_per_week': 38.0,
            'full_time_required_hours': 38.0,
            'attendance_ids': [(5, 0, 0)] + [(0, 0, {
                'dayofweek': dayofweek,
                'hour_from': hour_from,
                'hour_to': hour_to,
                'work_entry_type_id': cls.env.ref('hr_work_entry.au_work_entry_type_attendance').id

            }) for dayofweek, hour_from, hour_to in [
                ("0", 8.0, 12.0),
                ("0", 13.0, 16.6),
                ("1", 8.0, 12.0),
                ("1", 13.0, 16.6),
                ("2", 8.0, 12.0),
                ("2", 13.0, 16.6),
                ("3", 8.0, 12.0),
                ("3", 13.0, 16.6),
                ("4", 8.0, 12.0),
                ("4", 13.0, 16.6),
            ]],
        }])
        cls.Logs = cls.env["l10n_au.audit.log"].sudo()
        cls.employee_user_1 = new_test_user(cls.env, login='mel')
        cls.employee_1 = cls.env["hr.employee"].create({
            "name": "Mel Gibson",
            "resource_calendar_id": cls.resource_calendar.id,
            "company_id": cls.company.id,
            "user_id": cls.employee_user_1.id,
            "work_phone": "123456789",
            "work_email": "mel@gmail.com",
            "private_phone": "123456789",
            "private_email": "mel@odoo.com",
            "private_street": "1 Test Street",
            "private_city": "Sydney",
            "private_state_id": cls.env.ref("base.state_au_2").id,
            "private_zip": "2000",
            "private_country_id": cls.env.ref("base.au").id,
            "birthday": date(2000, 1, 1),
            "l10n_au_tfn_declaration": "provided",
            "l10n_au_tfn": "999999661",
            "l10n_au_tax_free_threshold": True,
            "sex": "male",
        })
        bank_account = cls.env['res.partner.bank'].create({
            "bank_name": "Commonwealth Bank of Australia",
            "bank_bic": "CTBAAU2S",
            "country_id": cls.env.ref("base.au").id,
            "account_number": '12344321',
            "clearing_label_id": cls.env.ref('base.clearing_label_au').id,
            "clearing_number": '123456',
            "company_id": cls.company.id,
            "partner_id": cls.company.partner_id.id,
        })
        cls.bank_journal = cls.env["account.journal"].create({
            "name": "Payslip Bank",
            "type": "bank",
            "aba_fic": "CBA",
            "aba_user_spec": "Test Ltd",
            "aba_user_number": "111111",
            "company_id": cls.company.id,
            "bank_account_id": bank_account.id,
        })

        cls.hr_group = cls.env["res.groups"].create({
            "name": "Test HR Group",
            "privilege_id": cls.env.ref("hr_payroll.res_groups_privilege_payroll").id,
            "implied_ids": cls.env.ref('base.group_user')
        })

    @classmethod
    def setup_independent_company(cls, **kwargs):
        return super().setup_independent_company(
            vat='85658499097',
            **kwargs,
        )

    def setUp(self):
        super().setUp()
        self.Logs.search([]).unlink()

    def _get_logs(self, record):
        logs = self.Logs.search([('log_description', 'ilike', f"(model: {record._name}, id:{record.id})")])
        return logs.mapped('log_description')

    def test_update_audit_logging(self):
        self.company.vat = "83914571673"
        company_logs = self._get_logs(self.company)

        self.assertIn(
            "%s - %s - %s was changed for %s by %s" % (self.company.l10n_au_bms_id,
                                                       self.company.name,
                                                       self.company._fields["vat"].string,
                                                       self.company._get_display_name(),
                                                       self.env.user.display_name),
            company_logs[0],
        )

    def test_create_user_audit_logging(self):
        test_group_user = self.env['res.users'].create({
            'name': 'Test Group User',
            'login': 'TestGroupUser',
            'group_ids': self.hr_group,
            'company_ids': self.company,
        })
        user_logs = self._get_logs(test_group_user)
        log_message = "%s - %s - %s was changed for %s by %s" % (self.company.l10n_au_bms_id,
                                                       self.company.name,
                                                       test_group_user._fields["company_ids"].string,
                                                       test_group_user._get_display_name(),
                                                       self.env.user.display_name)
        self.assertTrue(any(log_message in log for log in user_logs), "There should be a log for setting the company")

        log_message = "%s - %s - %s was changed for %s by %s" % (self.company.l10n_au_bms_id,
                                                       self.company.name,
                                                       test_group_user._fields["password"].string,
                                                       test_group_user._get_display_name(),
                                                       self.env.user.display_name)
        self.assertTrue(any(log_message in log for log in user_logs), "There should be a log for setting the company")

        log_message = f"User Test Group User (model: res.users, id:{test_group_user.id}) was granted access to group Payroll / Test HR Group by OdooBot"
        self.assertTrue(any(log_message in log for log in user_logs), "There should be a log for adding Payroll / Administrator group")

    def test_user_groups_audit_logging(self):
        user = self.employee_user_1
        # Write on res.group user_ids
        with self.with_user("admin"):
            self.hr_group.user_ids += user
        user_logs = self._get_logs(user)
        log_message = f"User mel (base.group_user) (model: res.users, id:{user.id}) was granted access to group {self.hr_group.display_name} by {self.env.user.display_name}"
        self.assertIn(log_message, user_logs[0], "There should be a log for adding Test HR Group group")

        self.Logs.search([]).unlink()
        # Write on res.users group_ids
        with self.with_user("admin"):
            user.group_ids -= self.hr_group
        user_logs = self._get_logs(user)
        log_message = f"User mel (base.group_user) (model: res.users, id:{user.id}) was removed from group {self.hr_group.display_name} by {self.env.user.display_name}"
        self.assertIn(log_message, user_logs[0], "There should be a log for removing Test HR Group group")

    def test_group_user_ids_link_command_audit_logging(self):
        """Adding/removing a user from the Groups form must be logged and must not raise IndexError."""
        user = new_test_user(self.env, login="jane")

        with self.with_user("admin"):
            self.hr_group.write({"user_ids": [Command.link(user.id)]})
        user_logs = self._get_logs(user)
        log_message = f"was granted access to group {self.hr_group.display_name} by {self.env.user.display_name}"
        self.assertTrue(
            any(log_message in log for log in user_logs),
            "There should be a log for adding the user to the group via a LINK command",
        )

        self.Logs.search([]).unlink()
        with self.with_user("admin"):
            self.hr_group.write({"user_ids": [Command.unlink(user.id)]})
        user_logs = self._get_logs(user)
        log_message = f"was removed from group {self.hr_group.display_name} by {self.env.user.display_name}"
        self.assertTrue(
            any(log_message in log for log in user_logs),
            "There should be a log for removing the user from the group via an UNLINK command",
        )

    def test_group_user_ids_multi_group_audit_logging(self):
        """Linking a user already in one written group into another must log only the new grant."""
        user = new_test_user(self.env, login="jane")
        hr_group_2 = self.env["res.groups"].create({
            "name": "Test HR Group Two",
            "privilege_id": self.env.ref("hr_payroll.res_groups_privilege_payroll").id,
        })
        with self.with_user("admin"):
            self.hr_group.write({"user_ids": [Command.link(user.id)]})
        self.Logs.search([]).unlink()

        with self.with_user("admin"):
            (self.hr_group | hr_group_2).write({"user_ids": [Command.link(user.id)]})
        user_logs = self._get_logs(user)
        self.assertEqual(len(user_logs), 1, "Only the newly granted group should be logged")
        log_message = f"was granted access to group {hr_group_2.display_name} by {self.env.user.display_name}"
        self.assertIn(log_message, user_logs[0], "There should be a log for granting the second group")

    def test_reified_groups_audit_logs(self):
        """Test that a change on a reified fields trigger the onchange of groups_id."""
        group_payroll_manager = self.env.ref('hr_payroll.group_hr_payroll_manager')

        user = self.employee_user_1
        with self.debug_mode():
            user_form = Form(user, view='base.view_users_form')

        user_form["group_ids"] = group_payroll_manager
        user_form.save()
        user_logs = self._get_logs(user)

        log_message = f"User mel (base.group_user) (model: res.users, id:{user.id}) was granted access to group Payroll / Administrator by {self.env.user.display_name}"
        self.assertTrue(any(log_message in log for log in user_logs), "There should be a log for adding Payroll / Administrator group")

    def test_sync_audit_logs(self):
        self.company.vat = "83914571673"
        with self.mock_register_request():
            self._register_company()
        with self.mock_audit_log_requests():
            self.Logs._sync_audit_logs()
