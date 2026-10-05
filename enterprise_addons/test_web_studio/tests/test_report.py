import json
from lxml import html
from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestReport(HttpCase):

    def test_new_report_with_address(self):
        self.authenticate("admin", "admin")
        response = self.url_open(
            '/web_studio/create_new_report',
            data=json.dumps({"params": {"model_name": "test.studio_report_model", "layout": "web.external_layout"}}),
            headers={"Content-Type": "application/json"}
        )
        result = response.json()["result"]
        report = self.env["ir.actions.report"].browse(result["id"])
        bismuth = self.env["res.partner"].create({
            "name": "Paul Bismuth",
            "vat": "FR67 110 010 014",
            "street": "42 rue de la Santé",
            "zip": "75014",
            "city": "Paris",
            "country_id": self.env.ref("base.fr").id,
        })
        test_record = self.env["test.studio_report_model"].create({"some_partner": bismuth.id, "some_company": self.env.company.id})
        html_arch, _ = report._render(report.id, [test_record.id])
        html_arch = html.fromstring(html_arch)
        self.assertEqual(len(html_arch.xpath("//div[@name='address']")), 1)

        self.assertEqual(html_arch.xpath("//div[@name='address']//address//*[@itemprop='name']")[0].text, "Paul Bismuth")
        self.assertEqual(html_arch.xpath("//div[@name='address']//address//*[@itemprop='streetAddress']")[0].text, "42 rue de la Santé")
