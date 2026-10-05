from odoo.tests.common import TransactionCase


class TestMergePartner(TransactionCase):

    def test_merge_partner_does_not_copy_ocr_flag(self):
        ocr_partner = self.env['res.partner'].create({
            'name': 'Partner X',
            'email': 'ocr_partner@example.com',
            'is_created_by_ocr': True,
        })
        regular_partner = self.env['res.partner'].create({
            'name': 'Partner X',
            'email': 'regular_partner@example.com',
            'is_created_by_ocr': False,
        })

        wizard = self.env['base.partner.merge.automatic.wizard'].create({})
        wizard._merge([ocr_partner.id, regular_partner.id], regular_partner)

        self.assertFalse(ocr_partner.exists())
        self.assertTrue(regular_partner.exists())
        self.assertFalse(regular_partner.is_created_by_ocr)
