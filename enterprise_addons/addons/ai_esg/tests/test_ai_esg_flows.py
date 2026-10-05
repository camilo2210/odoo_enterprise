from odoo import fields, Command
from odoo.addons.ai.tests.common import TestAICommon


class TestAiEsgFlows(TestAICommon):

    def test_ai_metrics_generation(self):
        nace = self.env['esg.nace'].create({
            'name': 'Information Technology (IT)',
            'code': 'M42.1.1',
        })
        wizard = self.env['metrics.ai.generation.wizard'].create({
            'company_id': self.env.company.id,
            'nace_id': nace.id,
            'company_size': 'large',
            'revenues_value': 2000000,
            'assets_value': 1000000,
            'core_business_description': """
                Odoo offers a suite of integrated business management applications (ERP, CRM, e-commerce, point-of-sale, accounting, inventory, project management, etc.).
                The mission is to give small to large companies access to “easy to use” applications that fulfill many business needs, with full integration across the apps.
                Odoo runs a dual model: a “Community” edition (open-source) and an “Enterprise” edition (proprietary/commercial) deployed either on-premises or as SaaS.
                The company was founded in Belgium (originally as TinyERP / OpenERP) and over time has expanded globally, building a partner network and serving businesses of all sizes.
            """
        })
        mocked_responses = [
            self.mock_text_response(
                r"""
                {
                    "items": [
                        {
                            "code": "E1-5",
                            "name": "Energy consumption and mix in SaaS operations",
                            "iros": {
                                "positive_impacts": ["Adopting energy-efficient cloud infrastructure for SaaS and on-premises deployments can reduce the company's indirect environmental footprint."],
                                "negative_impacts": ["Operating global data centers and office facilities increases electricity demand, potentially leading to higher GHG emissions depending on energy sources."],
                                "risks": ["Rising energy costs or stricter energy regulations in key markets (e.g., Belgium, US, France) could increase operational expenses."],
                                "opportunities": ["Switching to renewable energy or partnering with green data center providers can enhance Odoo's brand and appeal to sustainability-minded customers."]
                            }
                        },
                        {
                            "code": "E1-6",
                            "name": "Scope 1, 2, 3 GHG emissions from global operations",
                            "iros": {
                                "positive_impacts": [],
                                "negative_impacts": ["Scope 2 emissions from offices and Scope 3 emissions from third-party data centers can contribute to the company's carbon footprint."],
                                "risks": ["Clients and partners (such as Acme Corporation and OpenWood) may require Odoo to report and reduce GHG emissions as part of procurement processes."],
                                "opportunities": ["Implementing emission reduction strategies and transparent reporting can help meet growing regulatory and customer expectations."]
                            }
                        },
                        {
                            "code": "S1-13",
                            "name": "Employee training and digital skills development",
                            "iros": {
                                "positive_impacts": ["Continuous upskilling in ERP, CRM, and cloud technologies supports employee growth and strengthens Odoo's innovation capacity."],
                                "negative_impacts": [],
                                "risks": ["Failure to provide adequate training in rapidly evolving IT fields could lead to talent attrition and decreased competitiveness."],
                                "opportunities": ["Offering advanced training programs can attract and retain top technical talent globally."]
                            }
                        }
                    ]
                }
                """),
        ]
        with self.mock_completion_request(mocked_responses) as mock_request:
            action = wizard.action_generate_metrics()
        self.assertEqual(mock_request.call_count, 1)
        metrics = self.env['metrics.ai.suggestion.wizard'].browse(action['res_id']).suggestion_line_ids
        self.assertEqual(len(metrics), 10)
        self.assertEqual(
            metrics.mapped('detail'),
            [
                "Adopting energy-efficient cloud infrastructure for SaaS and on-premises deployments can reduce the company's indirect environmental footprint.",
                'Operating global data centers and office facilities increases electricity demand, potentially leading to higher GHG emissions depending on energy sources.',
                'Rising energy costs or stricter energy regulations in key markets (e.g., Belgium, US, France) could increase operational expenses.',
                "Switching to renewable energy or partnering with green data center providers can enhance Odoo's brand and appeal to sustainability-minded customers.",
                "Scope 2 emissions from offices and Scope 3 emissions from third-party data centers can contribute to the company's carbon footprint.",
                'Clients and partners (such as Acme Corporation and OpenWood) may require Odoo to report and reduce GHG emissions as part of procurement processes.',
                'Implementing emission reduction strategies and transparent reporting can help meet growing regulatory and customer expectations.',
                "Continuous upskilling in ERP, CRM, and cloud technologies supports employee growth and strengthens Odoo's innovation capacity.",
                'Failure to provide adequate training in rapidly evolving IT fields could lead to talent attrition and decreased competitiveness.',
                'Offering advanced training programs can attract and retain top technical talent globally.',
            ]
        )

    def test_ai_auto_assignment_emission_factor(self):
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.env.user.partner_id.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [
                Command.create({
                    'quantity': 1,
                }),
            ],
        })
        emission_source = self.env['esg.emission.source'].create({
            'name': 'Test Emission Source',
            'scope': 'direct',
        })
        emission_factor = self.env['esg.emission.factor'].create({
            'name': 'Test Emission Factor',
            'source_id': emission_source.id,
        })
        bill_line = bill.invoice_line_ids
        bill.action_post()
        action = self.env.ref('ai_esg.emission_factors_ai_auto_assignment')
        tool_1 = self.env.ref('ai_esg.ir_actions_server_ai_esg_get_emission_sources')
        tool_2 = self.env.ref('ai_esg.ir_actions_server_ai_esg_get_emission_factor')
        tool_3 = self.env.ref('ai_esg.ir_actions_server_ai_esg_assign_emission_factors_to_carbon_line')
        mocked_responses = [
            self.mock_tool_response(tool_1, {'scope': 'direct'}),
            self.mock_tool_response(tool_2, {'source_ids': [emission_source.id]}),
            self.mock_tool_response(tool_3, {'factor_id': emission_factor.id}),
            self.mock_text_response("Done"),
        ]
        self.env.cr.flush()  # Needed to force the emission line to be stored in DB
        self.assertTrue(self.env['esg.carbon.emission.report'].browse(-bill_line.id).exists())
        with self.mock_completion_request(mocked_responses) as mock_request:
            action.with_context(active_model='esg.carbon.emission.report', active_id=-bill_line.id).run()
        self.assertEqual(mock_request.call_count, 4)
        self.assertEqual(bill_line.esg_emission_factor_id, emission_factor)
