from odoo.tests import HttpCase, RecordCapturer, tagged


@tagged('post_install', '-at_install')
class TestServiceRequestsForm(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.country = cls.env.ref('base.us')
        cls.state = cls.env.ref('base.state_us_5')
        cls.role = cls.env['planning.role'].create({'name': 'Repair'})
        cls.website = cls.env.ref('base.default_website')
        cls.website.company_id.website_planning_field_service = True

    def _submit(self, files=None, **overrides):
        data = {
            'partner_name': 'Jane Doe',
            'partner_phone': '+12025551234',
            'partner_email': 'jane@example.com',
            'partner_company_name': '',
            'street': '742 Evergreen Terrace',
            'street2': '',
            'city': 'Springfield',
            'zip': '12345',
            'country_id': str(self.country.id),
            'state_id': str(self.state.id),
            'role_id': str(self.role.id),
            'priority': '0',
            'name': 'Need help',
            **overrides,
        }
        response = self.url_open('/website/form/planning.slot', data=data, files=files)
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertIn('id', payload, f"Form submission rejected: {payload}")
        return self.env['planning.slot'].browse(payload['id'])

    def _make_partner(self, **overrides):
        return self.env['res.partner'].create({
            'name': 'Jane Doe',
            'email': 'jane@example.com',
            'phone': '+12025551234',
            'street': '742 Evergreen Terrace',
            'city': 'Springfield',
            'zip': '12345',
            'country_id': self.country.id,
            'state_id': self.state.id,
            **overrides,
        })

    def test_submission_creates_slot_and_new_partner(self):
        with RecordCapturer(self.env['res.partner']) as capt:
            slot = self._submit()
        new_partners = capt.records
        self.assertEqual(len(new_partners), 1, "Exactly one partner should be created for a fresh submission")
        self.assertEqual(slot.partner_id, new_partners, "Slot should be linked to the newly created partner")
        self.assertFalse(new_partners.parent_id, "Fresh partner should be top-level, not a child contact")
        self.assertEqual(new_partners.email, 'jane@example.com', "Partner email should be carried over from the form")
        self.assertEqual(new_partners.phone, '+12025551234', "Partner phone should be carried over from the form")
        self.assertEqual(new_partners.street, '742 Evergreen Terrace', "Partner street should be carried over from the form")
        self.assertFalse(slot.start_datetime, "Form-submitted slot must have no planned start datetime")
        self.assertFalse(slot.end_datetime, "Form-submitted slot must have no planned end datetime")
        self.assertEqual(slot.role_id, self.role, "Slot role should reflect the submitted Type of Request")
        self.assertEqual(slot.name, 'Need help', "Without custom fields, the note should contain only the submitted description")

    def test_submission_creates_child_contact_for_new_address(self):
        existing = self._make_partner(street='1 Old Street', city='Othertown', zip='99999')
        with RecordCapturer(self.env['res.partner']) as capt:
            slot = self._submit()
        child = capt.records
        self.assertEqual(len(child), 1, "Exactly one child contact should be created for a new address")
        self.assertEqual(child.parent_id, existing, "Child contact should be attached to the email-matched partner")
        self.assertEqual(child.type, 'delivery', "Address-only child contact should be a delivery address")
        self.assertEqual(child.street, '742 Evergreen Terrace', "Child contact should carry the submitted street")
        self.assertEqual(child.city, 'Springfield', "Child contact should carry the submitted city")
        self.assertEqual(slot.partner_id, child, "Slot should be linked to the newly created child contact, not the parent")

    def test_submission_reuses_existing_child_contact_for_known_address(self):
        parent = self._make_partner(street='1 Old Street', city='Othertown', zip='99999')
        site = self.env['res.partner'].create({
            'name': 'Site B',
            'parent_id': parent.id,
            'type': 'delivery',
            'street': '742 Evergreen Terrace',
            'city': 'Springfield',
            'zip': '12345',
            'country_id': self.country.id,
            'state_id': self.state.id,
        })
        with RecordCapturer(self.env['res.partner']) as capt:
            slot = self._submit()
        self.assertEqual(slot.partner_id, site, "Existing child contact whose address matches the form should be reused")
        self.assertFalse(capt.records, "No new partner should be created when a child contact already matches")

    def test_submission_writes_photo_count_to_note_and_custom_fields_to_chatter(self):
        png = b'\x89PNG\r\n\x1a\n' + b'\x00' * 50
        slot = self._submit(
            files=[
                ('photos[0]', ('damage.png', png, 'image/png')),
                ('photos[1]', ('serial.png', png, 'image/png')),
            ],
            additional_info='Gate code is 4815',
        )
        self.assertEqual(
            slot.name,
            'Need help\n\n2 photo(s) attached',
            "The note should hold the description and the photo count, not the custom fields",
        )
        custom_message = slot.message_ids.filtered(lambda m: 'Other Information' in (m.body or ''))
        self.assertTrue(custom_message, "Custom fields should be logged in the chatter")
        self.assertIn('additional_info : Gate code is 4815', custom_message.body, "The custom field should appear in the chatter")
        self.assertNotIn('Jane Doe', custom_message.body, "Partner-related inputs must not leak into the chatter")
        self.assertNotIn('742 Evergreen', custom_message.body, "Partner-related inputs must not leak into the chatter")
        attachments = self.env['ir.attachment'].search([('res_model', '=', 'planning.slot'), ('res_id', '=', slot.id)])
        self.assertEqual(sorted(attachments.mapped('name')), ['damage.png', 'serial.png'], "Uploaded photos should be attached to the slot")

    def test_feature_gated_per_company(self):
        """The form page, thank-you page and submission endpoint are only served
        when the current website's company has enabled the feature."""
        self.assertEqual(self.url_open('/service-requests').status_code, 200, "Form page should be reachable when enabled")
        with RecordCapturer(self.env['planning.slot']) as capt:
            self.website.company_id.website_planning_field_service = False
            self.assertEqual(self.url_open('/service-requests').status_code, 404, "Form page must 404 when disabled")
            self.assertEqual(self.url_open('/service-requests/submitted').status_code, 404, "Thank-you page must 404 when disabled")
            blocked = self.url_open('/website/form/planning.slot', data={'role_id': str(self.role.id), 'name': 'Need help'})
            self.assertEqual(blocked.status_code, 404, "Submission must be rejected when disabled")
        self.assertFalse(capt.records, "No slot should be created while the feature is disabled")
