# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.addons.ai.tests.common import mock_iap_results, TestAICommon
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestAIOpenMenuGraphTour(HttpCase, TestAICommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Minimal graph arch on res.partner to match what the mocked LLM
        # will ask for (`create_date` at `month` interval).
        cls.test_graph_view = cls.env['ir.ui.view'].create({
            'name': 'res.partner.ai.test.graph',
            'model': 'res.partner',
            'type': 'graph',
            'arch': """
                <graph>
                    <field name="create_date" type="row" interval="month"/>
                </graph>
            """,
        })

        # _ai_tool_open_menu_graph requires "graph" in action.views.
        cls.test_action = cls.env['ir.actions.act_window'].create({
            'name': 'AI Test Contacts',
            'res_model': 'res.partner',
            'view_mode': 'graph',
        })

        # Parent under the Discuss app's Configuration menu.
        cls.test_menu = cls.env['ir.ui.menu'].create({
            'name': 'AI Test Contacts',
            'parent_id': cls.env.ref('mail.menu_configuration').id,
            'action': f'ir.actions.act_window,{cls.test_action.id}',
            'sequence': 99,
        })

        # Retarget systray_ai_button to our test agent.
        cls.env['ai.composer'].sudo().search([
            ('focused_model_id', '=', False),
            ('interface_key', '=', 'systray_ai_button'),
        ]).ai_agent_id = cls.agent.id

        cls.open_menu_graph_tool = cls.env.ref('ai.ir_actions_server_open_menu_graph')

    def test_open_menu_graph_applies_date_groupby(self):
        tool_args = {
            'menu_id': self.test_menu.id,
            'model_name': 'res.partner',
            'selected_filters': [],
            'selected_groupbys': [
                {'field_name': 'create_date', 'intervals': ['month']},
            ],
            'measure': '__count',
            'mode': 'bar',
            'order': 'ASC',
            'search': [],
        }
        iap_results = [
            self.mock_tool_response(self.open_menu_graph_tool, args=tool_args),
            self.mock_text_response("Here is your graph"),
        ]

        # open_menu_graph is skill-gated in production; expose it as a default tool here.
        with self.mock_default_tools(self.open_menu_graph_tool), \
             mock_iap_results(self.env, iap_results):
            self.start_tour(
                "/odoo",
                "ai_open_menu_graph_tour",
                login="admin",
            )
