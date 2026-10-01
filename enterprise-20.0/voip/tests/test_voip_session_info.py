# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json
from uuid import uuid4

from odoo import Command
from odoo.tests import tagged, common


@tagged("-at_install", "post_install")
class TestVoipSessionInfo(common.HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.country_be = cls.env.ref("base.be")
        cls.country_cn = cls.env.ref("base.cn")
        cls.company_a = cls.env["res.company"].create({
            "name": "Company A",
            "country_id": cls.country_be.id,
        })
        cls.company_b = cls.env["res.company"].create({
            "name": "Company B",
            "country_id": cls.country_cn.id,
        })

        cls.user_password = "password"
        cls.user = common.new_test_user(
            cls.env,
            "voip_session",
            email="voip_session@test.com",
            password=cls.user_password,
            tz="UTC",
        )
        cls.user.write({
            "company_id": cls.company_a.id,
            "company_ids": [Command.set((cls.company_a + cls.company_b).ids)],
        })

        cls.payload = json.dumps(dict(jsonrpc="2.0", method="call", id=str(uuid4())))
        cls.headers = {"Content-Type": "application/json"}

    def test_session_info_has_country_id(self):
        """Verifies that voip's session_info override adds country_id to allowed companies."""
        self.authenticate(self.user.login, self.user_password)
        self.env["res.users.settings"]._find_or_create_for_user(self.user)
        response = self.url_open(
            "/web/session/get_session_info", data=self.payload, headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)

        result = response.json()["result"]
        user_companies = result["user_companies"]
        allowed = user_companies["allowed_companies"]

        company_a_data = allowed[str(self.company_a.id)]
        self.assertIn("country_id", company_a_data)
        self.assertEqual(company_a_data["country_id"], self.country_be.id)

        company_b_data = allowed[str(self.company_b.id)]
        self.assertIn("country_id", company_b_data)
        self.assertEqual(company_b_data["country_id"], self.country_cn.id)
