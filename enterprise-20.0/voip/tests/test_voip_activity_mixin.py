from odoo.exceptions import UserError
from odoo.tests import common, tagged


@tagged("voip", "post_install", "-at_install")
class TestVoipActivityMixin(common.TransactionCase):
    """`res.partner` is the only model inheriting `voip.activity.mixin` today."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_with_phone = cls.env["res.partner"].create({
            "name": "Callable partner",
            "phone": "+32485000001",
        })
        cls.partner_without_phone = cls.env["res.partner"].create({
            "name": "No phone partner",
        })

    def test_create_call_activity_adds_a_phonecall_activity(self):
        activities = self.partner_with_phone.create_call_activity()

        self.assertEqual(len(activities), 1)
        self.assertEqual(activities.res_id, self.partner_with_phone.id)
        self.assertEqual(activities.activity_type_id.category, "phonecall")

    def test_create_call_activity_on_empty_recordset_is_a_noop(self):
        activities = self.env["res.partner"].browse().create_call_activity()

        self.assertFalse(activities)

    def test_create_call_activity_raises_for_records_without_a_phone(self):
        with self.assertRaisesRegex(UserError, "do not have a phone number"):
            self.partner_without_phone.create_call_activity()

        activity = self.env["mail.activity"].search([
            ("res_model", "=", self.partner_without_phone._name),
            ("res_id", "=", self.partner_without_phone.id),
            ("activity_type_id.category", "=", "phonecall"),
        ])
        self.assertFalse(activity)
