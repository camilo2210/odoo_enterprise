# Part of Odoo. See LICENSE file for full copyright and licensing details.

from markupsafe import Markup

from odoo import Command, api, models
from odoo.addons.ai.utils.ai_fields_tools import ai_field_insert


class AiDocumentsSort(models.TransientModel):
    _inherit = "ai_documents.sort"

    @api.model
    def default_get(self, fields):
        values = super().default_get(fields)
        _ = self.env._

        if "ai_sort_prompt" not in fields:
            return values

        if "folder_id" in values:
            existing_ir_action = self.env["ir.actions.server"].search(
                [("ai_autosort_folder_id", "=", values["folder_id"])],
                limit=1,
            )

            if existing_ir_action:
                # Don't set the default prompt
                return values

        if "ai_tool_ids" not in values:
            values["ai_tool_ids"] = [Command.set([])]

        create_vendor_bill = self.env.ref("documents_account.ir_actions_server_create_vendor_bill", raise_if_not_found=False)
        create_customer_invoice = self.env.ref("documents_account.ir_actions_server_create_customer_invoice", raise_if_not_found=False)
        prompt_lines = [values.get("ai_sort_prompt", "")]
        if create_customer_invoice:
            prompt_lines.append(_("If it is a customer invoice, trigger the action to create one."))
            values["ai_tool_ids"][0][2].append(create_customer_invoice.id)

        if create_vendor_bill:
            prompt_lines.append(
                _(
                    "If the customer is %s it means it is a vendor bill, trigger the Create Vendor Bill action.",
                    ai_field_insert("company_id.name", _("Company > Name")),
                ),
            )
            values["ai_tool_ids"][0][2].append(create_vendor_bill.id)

        # Change the default value for the prompt
        values["ai_sort_prompt"] = Markup("<br/>").join(prompt_lines)
        return values

    @api.model
    def _get_demo_prompt_data(self):
        """Extend demo prompt with account prompts."""
        other_prompt_lines, ai_tool_ids = super()._get_demo_prompt_data()
        _ = self.env._

        create_vendor_bill = self.env.ref(
            "documents_account.ir_actions_server_create_vendor_bill",
            raise_if_not_found=False,
        )
        finance_folder = self.env.ref("documents.document_finance_folder", raise_if_not_found=False)
        legal_folder = self.env.ref("documents.document_legal_folder", raise_if_not_found=False)
        insurances_folder = self.env.ref("documents.document_insurances_folder", raise_if_not_found=False)
        ai_folder_insert = self.env["documents.document"]._ai_folder_insert

        # Collect account prompts in a local list to prepend them
        prompt_lines = []

        if finance_folder and create_vendor_bill:
            ai_tool_ids |= create_vendor_bill
            prompt_lines.append(_("If the document is an invoice, trigger the Vendor Bill action after moving it."))

        prompt_lines.append(Markup("""
            <div>%(instruction_1)s</div>
            <ul>
                <li>%(instruction_2)s</li>
                <li>%(instruction_3)s</li>
            </ul>
        """) % {
            "instruction_1": _(
                "If the document is not an invoice, move it to the correct folder:",
            ),
            "instruction_2": _(
                "Contracts & NDAs go to the %(legal)s folder.",
                legal=ai_folder_insert(legal_folder.id),
            ),
            "instruction_3": _(
                "Insurance contracts go to the %(insurance)s folder.",
                insurance=ai_folder_insert(insurances_folder.id),
            ),
        })

        # Prepend account prompts before other module prompts (e.g., fleet)
        return other_prompt_lines + prompt_lines, ai_tool_ids
