from odoo.addons.sale.tests.common import SaleCommon


class TestVoipSaleCommon(SaleCommon):
    """Base class for voip_sale tests."""
    _test_user_groups = SaleCommon._test_user_groups + ('voip.group_voip_officer',)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.parent_partner = cls.env["res.partner"].create({
            "name": "we are family",
            "phone": "+1233211234567",
        })
        cls.partner.parent_id = cls.parent_partner
        cls.child_partner = cls.env["res.partner"].create({
            "name": "child partner",
            "parent_id": cls.parent_partner.id,
        })
