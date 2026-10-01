from odoo.tests import Form, new_test_user, tagged
from odoo.tests.common import TransactionCase


@tagged("-at_install", "post_install")
class TestVoipHrWizardAccess(TransactionCase):
    def test_non_hr_user_can_open_log_call_wizard(self):
        """A user without HR rights must be able to open the log call wizard.

        The employee_id_domain compute reads res.partner.employee_ids, a field
        restricted to hr.group_hr_user. Without a guard, opening the wizard
        raises an AccessError for non-HR users.
        """
        partner = self.env["res.partner"].create({"name": "Test Partner"})
        non_hr_user = new_test_user(self.env, login="non_hr_user")
        call = self.env["voip.call"].create({
            "phone_number": "+1234567890",
            "partner_id": partner.id,
            "user_id": non_hr_user.id,
        })

        with Form.from_action(
            self.env(user=non_hr_user.id),
            call.with_user(non_hr_user).action_log_call(),
        ) as form:
            self.assertEqual(form.contact_id, partner)
