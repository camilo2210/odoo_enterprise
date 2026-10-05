# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.ai.tests.common import mock_iap_results, TestAICommon
from odoo.tests import tagged, HttpCase


@tagged("post_install", "-at_install")
class TestNaturalLanguageQueryUI(HttpCase, TestAICommon):
    def test_natural_language_query_with_date_filters(self):
        all_tasks_menu = self.env.ref("project.menu_project_management_all_tasks")
        open_list_tool = self.env.ref("ai.ir_actions_server_open_menu_list")
        adjust_search_tool = self.env.ref("ai.ir_actions_server_adjust_search")
        mock_responses = [
            # Mock LLM response with tool call to open_menu_list
            self.mock_tool_response(open_list_tool, args={
                "menu_id": all_tasks_menu.id,
                "model_name": "project.task",
                "selected_filters": [],
                "selected_groupbys": [
                    {
                        "field_name": "date_deadline",
                        "intervals": ["month"],
                    }
                ],
                "search": [],
            }),
            self.mock_text_response("Done"),
            # Second mock response: adjust search to kanban with date filter
            self.mock_tool_response(adjust_search_tool, args={
                "model_name": "project.task",
                "remove_facets": [],
                "toggle_filters": [
                    {
                        "field_name": "date_deadline",
                        "selected_periods": [
                            "first_quarter"
                        ],
                    },
                ],
                "toggle_groupbys": [],
                "apply_searches": [],
                "measures": [],
                "switch_view_type": "kanban",
            }),
            self.mock_text_response("Done"),
        ]
        with (
            mock_iap_results(self.env, mock_responses, channel_name="Monthly Task Analysis"),
            self.mock_default_tools(open_list_tool | adjust_search_tool),
        ):
            self.start_tour(
                "/odoo",
                "test_natural_language_query_with_date_groupby",
                login="admin",
            )
