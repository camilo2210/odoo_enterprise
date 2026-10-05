from odoo.addons.whatsapp.tests.common import MockIncomingWhatsApp, WhatsAppCommon
from odoo.tests import tagged


@tagged('wa_bsuid')
class TestWhatsAppBsuid(WhatsAppCommon, MockIncomingWhatsApp):

    def test_bsuid_is_scoped_per_account(self):
        """The same partner keeps a distinct BSUID per WhatsApp account (the point of the relation)."""
        sender_phone = '+32468000060'
        bsuid_1 = 'BE.account1uid'
        bsuid_2 = 'BE.account2uid'

        with self.mockWhatsappGateway():
            self._receive_whatsapp_message(self.whatsapp_account, 'Hi', sender_phone, sender_bsuid=bsuid_1)
        with self.mockWhatsappGateway():
            self._receive_whatsapp_message(self.whatsapp_account_2, 'Hi', sender_phone, sender_bsuid=bsuid_2)

        partner = self.env['res.partner'].search([('phone', '=', sender_phone)])
        self.assertEqual(len(partner), 1, "Both inbounds should resolve to the same partner (matched by phone)")
        # one BSUID stored per account, neither clobbering the other
        self.assertEqual(len(partner.wa_bsuid_ids), 2)
        self.assertEqual(partner.with_context(whatsapp_account_id=self.whatsapp_account).wa_bsuid, bsuid_1)
        self.assertEqual(partner.with_context(whatsapp_account_id=self.whatsapp_account_2).wa_bsuid, bsuid_2)

    def test_channel_found_by_wa_id_when_number_format_mismatches(self):
        """Make sure we fall back on wa_id if the phone format is somehow different."""
        wa_id = '32468000040'
        partner = self.env['res.partner'].create({'name': 'Known WaId User', 'wa_id': wa_id})
        existing_channel = self.env['discuss.channel'].sudo()._get_whatsapp_channel_from_identifiers(
            self.whatsapp_account, {'number': '+32468000040', 'wa_id': wa_id},
            sender_name='wa_id contact', create_if_not_found=True, related_message=False
        )
        self.assertEqual(existing_channel.whatsapp_partner_id, partner)
        self.assertEqual(existing_channel.whatsapp_partner_id.phone, '+32468000040')
        self.assertFalse(existing_channel.whatsapp_partner_id.wa_bsuid_ids)
        self.assertEqual(existing_channel.whatsapp_partner_id.wa_id, wa_id)
        self.assertEqual(existing_channel.whatsapp_number, '32468000040')

        found_channel = self.env['discuss.channel'].sudo()._get_whatsapp_channel_from_identifiers(
            self.whatsapp_account,
            {'number': '+321468000040', 'wa_id': wa_id},  # new phone digit is added for all numbers of this country
            sender_name='Known WaId User',
            create_if_not_found=True,
        )
        self.assertEqual(found_channel, existing_channel)
        self.assertEqual(found_channel.whatsapp_number, '32468000040')
        self.assertEqual(partner.phone, '+32468000040')  # not updated because we don't know if user updated it on purpose

    def test_receive_creates_partner_and_channel(self):
        """An inbound message resolves to a partner+channel for each identifier combination."""
        belgium = self.env.ref('base.be')
        cases = [
            (
                'bsuid-only, no sender name',
                {'sender_bsuid': 'BE.11111111111111111'},
                {'bsuid': 'BE.11111111111111111', 'phone': False, 'country_id': belgium},
            ),
            (
                'bsuid-only, with sender name',
                {'sender_bsuid': 'BE.22222222222222222', 'sender_name': 'Hidden User'},
                {'bsuid': 'BE.22222222222222222', 'phone': False, 'country_id': belgium, 'name': 'Hidden User'},
            ),
            (
                'phone + bsuid',
                {'sender_phone_number': '+32468000011', 'sender_bsuid': 'BE.33333333333333333',
                 'sender_name': 'Both Fields User'},
                {'bsuid': 'BE.33333333333333333', 'phone': '+32468000011'},
            ),
        ]
        for description, receive_kwargs, expected in cases:
            with self.subTest(description=description):
                with self.mockWhatsappGateway():
                    self._receive_whatsapp_message(self.whatsapp_account, 'Hello', **receive_kwargs)
                partner = self.env['res.partner'].search([('wa_bsuid_ids.bsuid', '=', expected['bsuid'])])
                self.assertEqual(len(partner), 1, "Partner should be created from the inbound message")
                self.assertEqual(partner.with_context(whatsapp_account_id=self.whatsapp_account).wa_bsuid, expected.pop('bsuid'))
                for field, value in expected.items():
                    self.assertEqual(partner[field], value, f"{field} should be {value!r}")
                channel = self.env['discuss.channel'].search([('whatsapp_partner_id', '=', partner.id)])
                self.assertEqual(len(channel), 1)
                self.assertTrue(channel.name, "Channel must have a non-empty name")

    def test_receive_reuses_existing_channel(self):
        """A second message from the same sender reuses the existing channel."""
        cases = [
            ('phone-only', {'sender_phone_number': '+32468000030'}, [('phone', '=', '+32468000030')]),
            ('bsuid-only', {'sender_bsuid': 'BE.77777777777777777'}, [('wa_bsuid_ids.bsuid', '=', 'BE.77777777777777777')]),
        ]
        for description, receive_kwargs, partner_domain in cases:
            with self.subTest(description=description):
                with self.mockWhatsappGateway():
                    self._receive_whatsapp_message(self.whatsapp_account, 'First', **receive_kwargs)
                    self._receive_whatsapp_message(self.whatsapp_account, 'Second', **receive_kwargs)
                partner = self.env['res.partner'].search(partner_domain)
                channels = self.env['discuss.channel'].search([('whatsapp_partner_id', '=', partner.id)])
                self.assertEqual(len(channels), 1, "Two messages from the same sender should reuse one channel")

    def test_receive_updates_partner_bsuid(self):
        """A bsuid arriving alongside a known phone is written onto the existing partner."""
        belgium_id = self.env.ref('base.be').id

        # Partner pre-existing in DB (e.g. created from the partner form).
        pre_partner = self.env['res.partner'].create({
            'name': 'Known Partner', 'phone': '+32468000020', 'country_id': belgium_id,
        })
        # Partner created by an earlier phone-only inbound.
        with self.mockWhatsappGateway():
            self._receive_whatsapp_message(self.whatsapp_account, 'Hello', '+32468000005')
        post_partner = self.env['res.partner'].search([('phone', '=', '+32468000005')])
        self.assertEqual(len(post_partner), 1, "Phone-only inbound should have created a partner")

        cases = [
            ('partner pre-existing with phone', pre_partner, '+32468000020', 'BE.55555555555555555555'),
            ('partner created by an earlier phone-only message',
             post_partner, '+32468000005', 'BE.88888888888888888'),
        ]
        for description, partner, sender_phone, bsuid in cases:
            with self.subTest(description=description):
                self.assertFalse(partner.with_context(whatsapp_account_id=self.whatsapp_account).wa_bsuid, "No bsuid before the bsuid-bearing message")
                with self.mockWhatsappGateway():
                    self._receive_whatsapp_message(
                        self.whatsapp_account, 'Hi', sender_phone, sender_bsuid=bsuid,
                    )
                self.assertEqual(partner.with_context(whatsapp_account_id=self.whatsapp_account).wa_bsuid, bsuid)

    def test_reply_uses_correct_recipient(self):
        """A reply via channel.message_post routes through the right identifier."""
        cases = [
            (
                'bsuid-only sender -> reply via bsuid',
                {'sender_bsuid': 'BE.88888888888888888'},
                {'kind': 'bsuid', 'bsuid': 'BE.88888888888888888', 'mobile_number': False},
            ),
            (
                'phone + bsuid sender -> reply via phone (number takes priority)',
                {'sender_phone_number': '+32468000040', 'sender_bsuid': 'BE.99999999999999999'},
                {'kind': 'number', 'bsuid': 'BE.99999999999999999', 'mobile_number': '+32468000040'},
            ),
        ]
        for description, receive_kwargs, expected in cases:
            with self.subTest(description=description):
                with self.mockWhatsappGateway():
                    self._receive_whatsapp_message(self.whatsapp_account, 'Hi', **receive_kwargs)
                partner = self.env['res.partner'].search([('wa_bsuid_ids.bsuid', '=', expected['bsuid'])])
                channel = self.env['discuss.channel'].search([('whatsapp_partner_id', '=', partner.id)])
                self.assertEqual(len(channel), 1)

                with self.mockWhatsappGateway():
                    wa_msg = channel.message_post(body='Reply', message_type='whatsapp_message').wa_message_ids
                    sent_recipients = self._wa_msg_sent_recipients

                self.assertEqual(len(wa_msg), 1)
                self.assertEqual(wa_msg.state, 'sent')
                # the message was actually sent through the expected identifier
                self.assertEqual(len(sent_recipients), 1)
                if expected['kind'] == 'number':
                    self.assertEqual(sent_recipients[0]['number'], wa_msg.mobile_number_formatted)
                    self.assertFalse(sent_recipients[0]['bsuid'])
                else:
                    self.assertEqual(sent_recipients[0]['bsuid'], wa_msg.recipient_wa_bsuid)
                    self.assertFalse(sent_recipients[0]['number'])
                self.assertEqual(wa_msg.recipient_wa_bsuid, expected['bsuid'])
                self.assertEqual(wa_msg.mobile_number, expected['mobile_number'])

    def test_same_bsuid_on_two_partners_does_not_crash(self):
        """Updating a partner with a bsuid used by another partner is fine."""
        account = self.whatsapp_account
        shared_bsuid = 'BE.111111111'
        sender_number = '32468000000'
        ResPartner = self.env['res.partner'].sudo().with_context(whatsapp_account_id=account)

        with self.mockWhatsappGateway():
            self._receive_whatsapp_message(account, 'Hi, I just saw your ad', sender_bsuid=shared_bsuid)
        incoming_partner = ResPartner.search([('wa_bsuid_ids', 'any', [('bsuid', '=', shared_bsuid)])])
        new_channel = self.env['discuss.channel'].search([('whatsapp_partner_id', '=', incoming_partner.id)])

        user_created_partner = ResPartner.create({'name': 'Known Number', 'phone': f'+{sender_number}'})
        # Send the template as a user not already part of the original channel so that replies are routed
        # to a new channel, matching the phone partner in priority
        self.assertNotIn(self.user_admin.partner_id, new_channel.channel_partner_ids)
        composer = self._instanciate_wa_composer_from_records(
            self.simple_whatsapp_template, user_created_partner, with_user=self.user_admin,
        )
        with self.mockWhatsappGateway():
            composer.action_send_whatsapp_template()

        # When sending a message directly to a number, whatsapp will include the number in replies
        with self.mockWhatsappGateway():
            self._receive_whatsapp_message(account, "Yes I'm interested", sender_phone_number=sender_number, sender_bsuid=shared_bsuid)

        self.assertEqual(incoming_partner.wa_bsuid, shared_bsuid, "Partner created from an incoming message should have a bsuid.")
        self.assertEqual(user_created_partner.wa_bsuid, shared_bsuid, "Receiving a reply should update the bsuid of the matching partner")

    def test_status_associates_bsuid_with_outbound(self):
        """A status webhook carrying user_id writes recipient_wa_bsuid onto the matching outbound."""
        sender_phone = '+32468000050'
        bsuid = 'BE.statusuid_01'

        with self.mockWhatsappGateway():
            self._receive_whatsapp_message(self.whatsapp_account, 'Hi', sender_phone)
        channel = self.env['discuss.channel'].search([('whatsapp_number', '=', sender_phone.lstrip('+'))])
        with self.mockWhatsappGateway():
            wa_msg = channel.message_post(body='Reply', message_type='whatsapp_message').wa_message_ids
        self.assertFalse(wa_msg.recipient_wa_bsuid, "No bsuid known yet at send time")

        self._receive_message_update(
            self.whatsapp_account,
            '12345678912',  # match the arbitrary value of receive_whatsapp_message
            extra_value={
                'statuses': [{'id': wa_msg.msg_uid, 'status': 'sent'}],
                'contacts': [{'wa_id': '32468000050', 'user_id': bsuid}],
            },
        )
        self.assertEqual(wa_msg.recipient_wa_bsuid, bsuid)
