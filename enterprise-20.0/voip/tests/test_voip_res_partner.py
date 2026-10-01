from odoo.addons.mail.tools.discuss import Store
from odoo.tests import common, tagged


@tagged("-at_install", "post_install")
class TestVoipResPartner(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.min_length = cls.env["res.partner"]._phone_search_min_length
        cls.partner1 = cls.env["res.partner"].create({
            "name": "Partner 1",
            "phone": "1" * (cls.min_length + 1),
        })
        cls.partner2 = cls.env["res.partner"].create({
            "name": "No matched name",
            "phone": "2" * (cls.min_length + 1),
            "email": "partner2@example.com",
        })
        cls.partner3 = cls.env["res.partner"].create({
            "name": "No matched name, no email",
            "phone": "3" * (cls.min_length + 1),
        })
        cls.partner4 = cls.env["res.partner"].create({
            "name": "partner 4",
            "phone": False,
            "email": "partner4@example.com",
        })

    def assertIdInStoreData(self, id, store_data):
        ids = [record['id'] for record in store_data.get("res.partner", [])]
        self.assertIn(id, ids)

    def assertIdNotInStoreData(self, id, store_data):
        ids = [record['id'] for record in store_data.get("res.partner", [])]
        self.assertNotIn(id, ids)

    def test_add_to_activity_queue_action(self):
        partners = self.env["res.partner"].create([
            {"name": "Activity Queue Partner 1", "phone": "+1 202-555-0100"},
            {"name": "Activity Queue Partner 2", "phone": "+1 202-555-0101"},
        ])
        action = self.env.ref("voip.action_add_to_activity_queue")

        self.assertEqual(action.model_id.model, "res.partner")
        self.assertEqual(action.binding_model_id.model, "res.partner")
        self.assertEqual(action.binding_view_types, "list,kanban")

        action.with_context(active_model="res.partner", active_ids=partners[:1].ids).run()
        # Running the action on a mixed selection only creates an activity for
        # the partner without one.
        action.with_context(active_model="res.partner", active_ids=partners.ids).run()

        activities = self.env["mail.activity"].search([
            ("res_model", "=", "res.partner"),
            ("res_id", "in", partners.ids),
            ("user_id", "=", self.env.uid),
            ("activity_type_id.category", "=", "phonecall"),
        ])
        self.assertEqual(len(activities), len(partners))
        self.assertEqual(set(activities.mapped("res_id")), set(partners.ids))

    def test_search_commercial_partners_active_test(self):
        company = self.env["res.partner"].create({"name": "Helper Company"})
        child = self.env["res.partner"].create({"name": "Child", "parent_id": company.id})
        grandchild = self.env["res.partner"].create({"name": "Grandchild", "parent_id": child.id})
        archived_child = self.env["res.partner"].create({"name": "Archived Child", "parent_id": company.id})
        archived_child.active = False
        outsider = self.env["res.partner"].create({"name": "Outsider"})

        everyone = child._search_commercial_partners(active_test=False)
        self.assertIn(company, everyone)
        self.assertIn(child, everyone)
        self.assertIn(grandchild, everyone)
        self.assertIn(archived_child, everyone)
        self.assertNotIn(outsider, everyone)

        actives = child._search_commercial_partners()
        self.assertIn(company, actives)
        self.assertIn(grandchild, actives)
        self.assertNotIn(archived_child, actives)
        self.assertNotIn(outsider, actives)

    def test_voip_get_contacts_search_by_name_or_email(self):
        """Test that partners are searched by name and email. Only partners with phone or mobile are returned."""
        store_data = self.env["res.partner"].get_contacts(
            offset=0,
            limit=10,
            search_terms="partner",
        ).as_dict()
        self.assertIdInStoreData(self.partner1.id, store_data)
        self.assertIdInStoreData(self.partner2.id, store_data)
        self.assertIdNotInStoreData(self.partner3.id, store_data)
        self.assertIdNotInStoreData(self.partner4.id, store_data)

    def test_voip_get_contacts_search_by_phone(self):
        store_data = self.env["res.partner"].get_contacts(
            offset=0,
            limit=10,
            search_terms="3" * self.min_length,
        ).as_dict()
        self.assertIdInStoreData(self.partner3.id, store_data)
        self.assertIdNotInStoreData(self.partner1.id, store_data)
        self.assertIdNotInStoreData(self.partner2.id, store_data)

    def test_voip_get_contacts_search_by_phone_sanitized(self):
        """Test that phone_sanitized =like search works correctly."""
        search_term = "+32111"
        # Before setting phone_sanitized, partner1 should NOT be found
        store_data = self.env["res.partner"].get_contacts(
            offset=0,
            limit=10,
            search_terms=search_term,
        ).as_dict()
        self.assertIdNotInStoreData(self.partner1.id, store_data)

        # Manually set phone_sanitized and re-search
        self.partner1.phone_sanitized = "+321111111"
        self.env.flush_all()
        store_data = self.env["res.partner"].get_contacts(
            offset=0,
            limit=10,
            search_terms=search_term,
        ).as_dict()
        self.assertIdInStoreData(self.partner1.id, store_data)

    def test_voip_get_contacts_search_by_T9_name(self):
        # "partner" in T9 is 7278637
        store_data = self.env["res.partner"].get_contacts(
            offset=0,
            limit=10,
            search_terms="7278637",
        ).as_dict()
        self.assertIdInStoreData(self.partner1.id, store_data)
        self.assertIdNotInStoreData(self.partner4.id, store_data)
        self.assertIdNotInStoreData(self.partner2.id, store_data)
        self.assertIdNotInStoreData(self.partner3.id, store_data)

    def test_voip_get_contacts_search_internal_users_first(self):
        limit = 13
        external_partners = self.env["res.partner"].create([
            {
                "name": f"VoIP Transfer External {index:02d}",
                "phone": f"44444444{index:03d}",
            }
            for index in range(limit)
        ])
        internal_user = common.new_test_user(self.env, login="voip_transfer_internal_user")
        internal_user.partner_id.write({
            "name": "VoIP Transfer Internal",
            "phone": "55555555555",
        })
        store_data = self.env["res.partner"].get_contacts(
            offset=0,
            limit=limit,
            search_terms="VoIP Transfer",
            internal_users_first=True,
        ).as_dict()
        ids = [record["id"] for record in store_data.get("res.partner", [])]
        self.assertEqual(ids[0], internal_user.partner_id.id)
        self.assertEqual(len(ids), limit)
        self.assertNotIn(external_partners[-1].id, ids)

    def test_voip_get_contacts_returns_prioritized_contacts(self):
        partner_a = self.env["res.partner"].create({
            "name": "VoIP Ranked Normal 00",
            "phone": "+32498111111",
        })
        partner_b = self.env["res.partner"].create({
            "name": "VoIP Ranked Pinned B",
            "phone": "+32498222222",
        })
        partner_c = self.env["res.partner"].create({
            "name": "VoIP Ranked Pinned C",
            "phone": "+32498333333",
        })
        incoming_partner = self.env["res.partner"].create({
            "name": "VoIP Ranked Z Incoming",
            "phone": "+32498444444",
        })
        old_partner = self.env["res.partner"].create({
            "name": "VoIP Ranked Z Old",
            "phone": "+32498555555",
        })
        normal_partners = self.env["res.partner"].create([
            {
                "name": f"VoIP Ranked Normal {index:02d}",
                "phone": f"+3249866666{index}",
            }
            for index in range(1, 4)
        ])

        calls = self.env["voip.call"].create([
            {
                "phone_number": partner_b.phone,
                "partner_id": partner_b.id,
                "user_id": self.env.uid,
            },
            {
                "phone_number": partner_b.phone,
                "partner_id": partner_b.id,
                "user_id": self.env.uid,
            },
            {
                "phone_number": partner_a.phone,
                "partner_id": partner_a.id,
                "user_id": self.env.uid,
            },
            {
                "phone_number": partner_c.phone,
                "partner_id": partner_c.id,
                "user_id": self.env.uid,
            },
            {
                "phone_number": old_partner.phone,
                "partner_id": old_partner.id,
                "user_id": self.env.uid,
            },
            *(
                {
                    "direction": "incoming",
                    "phone_number": incoming_partner.phone,
                    "partner_id": incoming_partner.id,
                    "user_id": self.env.uid,
                }
                for _ in range(3)
            ),
        ])
        for call, create_date in zip(
            calls,
            [
                "2026-03-01 12:00:00",
                "2026-03-02 12:00:00",
                "2026-03-05 12:00:00",
                "2026-03-10 12:00:00",
                "2026-02-01 12:00:00",
                "2026-03-07 12:00:00",
                "2026-03-08 12:00:00",
                "2026-03-09 12:00:00",
            ],
        ):
            self.env.cr.execute(
                "UPDATE voip_call SET create_date = %s WHERE id = %s",
                (create_date, call.id),
            )
        calls.invalidate_recordset(["create_date"])

        first_page = self.env["res.partner"].get_contacts(
            offset=0,
            limit=3,
            search_terms="VoIP Ranked",
            prioritized_contacts_limit=2,
        )
        second_page = self.env["res.partner"].get_contacts(
            offset=3,
            limit=3,
            search_terms="VoIP Ranked",
            prioritized_contacts_limit=2,
        )

        self.assertEqual(
            first_page["prioritized_contact_ids"],
            [partner_c.id, incoming_partner.id],
        )
        self.assertNotIn(old_partner.id, first_page["prioritized_contact_ids"])

        first_page_partner_ids = [
            record["id"] for record in first_page["store_data"].as_dict()["res.partner"]
        ]
        self.assertEqual(
            set(first_page_partner_ids),
            {partner_a.id, partner_c.id, incoming_partner.id},
        )

        second_page_partner_ids = [
            record["id"] for record in second_page["store_data"].as_dict()["res.partner"]
        ]
        self.assertEqual(
            set(second_page_partner_ids),
            set(normal_partners.ids),
        )

    def test_voip_get_contacts_phone_search_min_length(self):
        """Test that phone search is only done when the search terms length is >= _phone_search_min_length."""
        if self.min_length <= 1:
            self.skipTest("_phone_search_min_length is set to 1, skipping test.")

        store_data = self.env["res.partner"].get_contacts(
            offset=0,
            limit=10,
            search_terms="1" * self.min_length,
        ).as_dict()
        self.assertIdInStoreData(self.partner1.id, store_data)

        store_data = self.env["res.partner"].get_contacts(
            offset=0,
            limit=10,
            search_terms="1" * (self.min_length - 1),
        ).as_dict()
        self.assertIdNotInStoreData(self.partner1.id, store_data)

    def test_voip_get_contacts_store_im_status_fields(self):
        user = common.new_test_user(self.env, login="voip_im_status_user")
        user.partner_id.write({"phone": "9999999999"})
        store_data = self.env["res.partner"].get_contacts(
            offset=0,
            limit=10,
            search_terms=user.partner_id.name,
        ).as_dict()
        self.assertIn("res.partner", store_data)
        partner_data = next(
            record for record in store_data["res.partner"] if record["id"] == user.partner_id.id
        )
        self.assertIn(user.id, partner_data["user_ids"])
        user_data = next(record for record in store_data["res.users"] if record["id"] == user.id)
        self.assertIn("im_status_access_token", user_data)

    def test_voip_get_contacts_store_active_call_visibility_on_user(self):
        user = common.new_test_user(self.env, login="voip_active_call_user")
        user.partner_id.write({"phone": "11111111111"})
        self.env["mail.presence"]._update_presence(user)
        self.env["voip.call"].create({
            "phone_number": "11111111111",
            "state": "ongoing",
            "user_id": user.id,
        })
        store_data = self.env["res.partner"].get_contacts(
            offset=0,
            limit=10,
            search_terms=user.partner_id.name,
        ).as_dict()
        partner_data = next(
            record for record in store_data["res.partner"] if record["id"] == user.partner_id.id
        )
        self.assertIn(user.id, partner_data["user_ids"])
        user_data = next(record for record in store_data["res.users"] if record["id"] == user.id)
        self.assertTrue(user_data["should_display_in_call_im_status"])

    def test_store_im_status_fields_store_active_call_visibility_on_user(self):
        user = common.new_test_user(self.env, login="voip_im_status_active_call_user")
        self.env["mail.presence"]._update_presence(user)
        self.env["voip.call"].create({
            "phone_number": "11111111111",
            "state": "ongoing",
            "user_id": user.id,
        })
        store_data = Store().add(user.partner_id, "_store_im_status_fields").as_dict()
        partner_data = next(
            record for record in store_data["res.partner"] if record["id"] == user.partner_id.id
        )
        self.assertIn(user.id, partner_data["user_ids"])
        user_data = next(record for record in store_data["res.users"] if record["id"] == user.id)
        self.assertTrue(user_data["should_display_in_call_im_status"])

    def test_voip_get_contacts_hides_active_call_for_manual_offline_user(self):
        user = common.new_test_user(self.env, login="voip_offline_call_user")
        user.partner_id.write({"phone": "22222222222"})
        self.env["voip.call"].create({
            "phone_number": "22222222222",
            "state": "ongoing",
            "user_id": user.id,
        })
        user.manual_im_status = "offline"
        store_data = self.env["res.partner"].get_contacts(
            offset=0,
            limit=10,
            search_terms=user.partner_id.name,
        ).as_dict()
        user_data = next(record for record in store_data["res.users"] if record["id"] == user.id)
        self.assertFalse(user_data["should_display_in_call_im_status"])
