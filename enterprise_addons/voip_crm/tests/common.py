from odoo.addons.sales_team.tests.common import TestSalesCommon


class TestVoipCrmCommon(TestSalesCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_no_opportunities = cls.env["res.partner"].create({
            "name": "Mahmoud El-khatib",
            "phone": "+1234567890",
            "email": "no.opportunities@test.example.com",
        })
        cls.partner_one_opportunity = cls.env["res.partner"].create({
            "name": "Hany El-sharqawi",
            "phone": "+1234567891",
            "email": "one.opportunity@test.example.com",
        })
        cls.partner_multiple_opportunities = cls.env["res.partner"].create({
            "name": "Mina Ezzat",
            "phone": "+1234567892",
            "email": "multiple.opportunities@test.example.com",
        })
        cls.opportunity_1 = cls.env["crm.lead"].create({
            "name": "Test Opportunity 1",
            "type": "opportunity",
            "partner_id": cls.partner_one_opportunity.id,
            "user_id": cls.user_sales_manager.id,
            "probability": 50,
        })
        cls.opportunity_2 = cls.env["crm.lead"].create({
            "name": "Test Opportunity 2",
            "type": "opportunity",
            "partner_id": cls.partner_multiple_opportunities.id,
            "user_id": cls.user_sales_manager.id,
            "probability": 30,
        })
        cls.opportunity_3 = cls.env["crm.lead"].create({
            "name": "Test Opportunity 3",
            "type": "opportunity",
            "partner_id": cls.partner_multiple_opportunities.id,
            "user_id": cls.user_sales_salesman.id,
            "probability": 70,
        })
        cls.call_no_partner = cls.env["voip.call"].create({
            "phone_number": "+1234567899",
        })
