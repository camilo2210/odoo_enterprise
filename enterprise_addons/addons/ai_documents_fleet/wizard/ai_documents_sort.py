# Part of Odoo. See LICENSE file for full copyright and licensing details.

from markupsafe import Markup

from odoo import _, Command, api, models


class AiDocumentsSort(models.TransientModel):
    _inherit = "ai_documents.sort"

    @api.model
    def default_get(self, fields):
        values = super().default_get(fields)
        _ = self.env._

        if "ai_sort_prompt" not in fields:
            return values

        if "folder_id" in values and self.env["ir.actions.server"].search(
                [("ai_autosort_folder_id", "=", values["folder_id"])],
                limit=1):
            return values

        if "ai_tool_ids" not in values:
            values["ai_tool_ids"] = [Command.set([])]

        fleet_link_action = self.env.ref(
            "ai_documents_fleet.ir_actions_server_fleet_link",
            raise_if_not_found=False,
        )
        fleet_folder = self.env.ref(
            "documents_fleet.document_fleet_folder",
            raise_if_not_found=False,
        )

        prompt_lines = [values.get("ai_sort_prompt", "")]

        if fleet_link_action and fleet_folder:
            values["ai_tool_ids"][0][2].append(fleet_link_action.id)
            prompt_lines.append(
                _("If the document contains license plate number, link the document with the vehicle with the same license plate.")
            )

        # Change the default value for the prompt
        values["ai_sort_prompt"] = Markup("<br/>").join(prompt_lines)
        return values

    @api.model
    def _get_demo_prompt_data(self):
        """Extend demo prompt with fleet prompt."""
        prompt_lines, ai_tool_ids = super()._get_demo_prompt_data()

        fleet_link_action = self.env.ref(
            "ai_documents_fleet.ir_actions_server_fleet_link",
            raise_if_not_found=False,
        )
        fleet_folder = self.env.ref(
            "documents_fleet.document_fleet_folder",
            raise_if_not_found=False,
        )

        if fleet_link_action and fleet_folder:
            ai_tool_ids |= fleet_link_action
            prompt_lines.append(
                _(
                    "If the document is a traffic fine, move it to the %(fleet)s folder and link it to the vehicle with the matching license plate.",
                    fleet=self.env["documents.document"]._ai_folder_insert(fleet_folder.id),
                )
            )

        return prompt_lines, ai_tool_ids
