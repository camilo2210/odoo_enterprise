from odoo.tests import tagged

from .common import TestVoipCrmCommon


@tagged("post_install", "-at_install")
class TestResPartner(TestVoipCrmCommon):

    def test_get_view_opportunities_action(self):
        allowed_methods = {
            "get_view_opportunities_action": lambda obj, **kwargs: obj.get_view_opportunities_action(**kwargs),
        }
        test_cases = [
            {
                "label": "no_opportunities",
                "input": self.partner_no_opportunities,
                "method": "get_view_opportunities_action",
                "args": {},
                "expected": {
                    "name": "Opportunities",
                    "res_model": "crm.lead",
                    "views": [[False, "form"]],
                    "res_id": False,
                    "context": {
                        "default_partner_id": self.partner_no_opportunities.id,
                    },
                    "commercial_partner_opportunity_count": 0,
                },
            },
            {
                "label": "one_opportunity",
                "input": self.partner_one_opportunity,
                "method": "get_view_opportunities_action",
                "args": {},
                "expected": {
                    "name": "Opportunities",
                    "res_model": "crm.lead",
                    "views": [[False, "form"]],
                    "res_id": self.opportunity_1.id,
                    "commercial_partner_opportunity_count": 1,
                },
            },
            {
                "label": "multiple_opportunities",
                "input": self.partner_multiple_opportunities,
                "method": "get_view_opportunities_action",
                "args": {},
                "expected": {
                    "name": "Opportunities",
                    "res_model": "crm.lead",
                    "views_not": [[False, "form"]],
                    "domain": self.partner_multiple_opportunities._get_contact_opportunities_domain(),
                    "commercial_partner_opportunity_count": 2,
                },
            },
            {
                "label": "call_with_no_partner",
                "input": self.call_no_partner.partner_id,
                "method": "get_view_opportunities_action",
                "args": {"phone": self.call_no_partner.phone_number},
                "expected": {
                    "name": "Opportunities",
                    "res_model": "crm.lead",
                    "views": [[False, "form"]],
                    "context": {
                        "default_phone": self.call_no_partner.phone_number,
                    },
                },
            },
        ]
        for case in test_cases:
            with self.subTest(case=case["label"]):
                method_name = case["method"]
                if method_name not in allowed_methods:
                    raise ValueError(f"Method '{method_name}' is not allowed in tests")
                action = allowed_methods[method_name](case["input"], **case["args"])
                expected = case["expected"]
                for key, value in expected.items():
                    if key == "views_not":
                        self.assertNotEqual(action["views"], value)
                    elif key == "context":
                        for ctx_key, ctx_val in value.items():
                            self.assertEqual(action["context"][ctx_key], ctx_val)
                    elif key == "commercial_partner_opportunity_count":
                        if hasattr(case["input"], "commercial_partner_opportunity_count"):  # Only check if input is a partner
                            self.assertEqual(case["input"].commercial_partner_opportunity_count, value)
                    elif key == "domain":
                        self.assertEqual(action["domain"], value)
                    else:
                        self.assertEqual(action[key], value)

    def test_commercial_partner_opportunity_count(self):
        parent_partner = self.env["res.partner"].create({
            "name": "Team Egypt",
            "phone": "+1233211234567",
        })
        (self.partner_no_opportunities | self.partner_one_opportunity | self.partner_multiple_opportunities).parent_id = parent_partner.id
        self.assertEqual((parent_partner | self.partner_no_opportunities | self.partner_one_opportunity | self.partner_multiple_opportunities).mapped("commercial_partner_opportunity_count"), [3, 3, 3, 3],
            "The commercial partner opportunity count should be the sum of all opportunities in this partner's family.")
