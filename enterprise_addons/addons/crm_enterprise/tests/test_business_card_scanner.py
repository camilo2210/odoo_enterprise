# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch
from odoo.tests.common import TransactionCase
from odoo.addons.crm_enterprise.tools.business_card_scanner import BusinessCardScanner


class TestBusinessCardScanner(TransactionCase):

    def test_business_cards_to_leads_lead_values(self):
        ocr_from_iap_response = {
            "partner_name": "Odoo",
            "contact_name": "Naruto Uzumaki",
            "email_from": "naruto@odoo.com",
            "phone": "9727602551",
            "website": "http://anime.com",
            "function": "Hokage",
            "street": "Ninja Street, near Ramen shop",
            "street2": "Hidden Leaf",
            "city": "Gandhinagar",
            "zip": "382007",
            "country_code": "IN",
            "state_code": "GJ",
        }
        attachment = self.env['ir.attachment'].create({
            'name': 'test_image.png',
            'mimetype': 'image/png',
            'raw': b'dummy image',
        })

        scanner = BusinessCardScanner(self.env)

        with patch.object(BusinessCardScanner, "_ocr_from_iap", return_value=ocr_from_iap_response):
            leads = scanner.business_cards_to_leads(attachment)
            lead = leads[0]

        expected = {
            k: v
            for k, v in ocr_from_iap_response.items()
            if k not in {"phone", "country_code", "state_code"}
        }
        self.assertEqual(
            {field: lead[field] for field in expected},
            expected,
        )

        country = self.env["res.country"].search([("code", "=", "IN")], limit=1)
        self.assertEqual(lead.country_id, country)

        state = self.env["res.country.state"].search([
            ("code", "=", "GJ"),
            ("country_id", "=", country.id),
        ], limit=1)
        self.assertEqual(lead.state_id, state)

        expected_phone = self.env["crm.lead"]._phone_format(
            number="+919727602551",
            country=country,
        )
        self.assertEqual(lead.phone, expected_phone)
