# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import logging

import psycopg2

from odoo import _, fields, models
from odoo.addons.ai.utils.ai_fields_tools import parse_ai_prompt_values
from odoo.exceptions import RedirectWarning

_logger = logging.getLogger(__name__)


class IrActionsServer(models.Model):
    _inherit = "ir.actions.server"

    ai_autosort_folder_id = fields.Many2one(
        "documents.document",
        string="Sorted Folder",
        domain=[("type", "=", "folder"), ("shortcut_document_id", "=", False)],
    )

    def _ai_action_run(self, record):
        self.ensure_one()
        if not self.ai_autosort_folder_id or record._name != 'documents.document':
            return super()._ai_action_run(record)

        record = record.with_context(ai_executed_action=self, ai_documents_skip_autosort=True, ai_max_pdf_pages=5)

        ret, tool_calls_history = [], []
        try:
            ret, tool_calls_history = super()._ai_action_run(record)
        except psycopg2.errors.SerializationFailure:
            raise
        except RedirectWarning as e:
            error = e.args[0]
            _logger.error("AI error: %s", error)
        except Exception as e:  # noqa: BLE001
            # We don't want to raise, to not break the flow like documents upload
            error = e
            _logger.error("AI error: %s", error)
        else:
            error = next((t["error"] for t in tool_calls_history if t["error"]), None)

        if error:
            if isinstance(record, self.pool['mail.thread']):
                record._message_log(body=_("AI: An error occurred: %s", error), author_id=self._ai_partner().id)

            if self.env.user.active:
                self.env.user._bus_send(
                    "ai_documents.auto_sort_notification",
                    {
                        "message": str(error),
                        "type": "warning",
                        "document_name": record.name,
                        "document_access_url": record.access_url,
                    },
                )

        elif self.env.user.active:
            # Send the last tool result or name as toast notification
            # Or the main AI action if no tool was executed
            tool_history = " ".join(t["result"] for t in tool_calls_history if t["result"])
            message = tool_history or self._ai_get_action_description(record)

            self.env.user._bus_send(
                "ai_documents.auto_sort_notification",
                {
                    "message": message,
                    "type": "success",
                    "document_name": record.name,
                    "document_access_url": record.access_url,
                },
            )
        return ret, tool_calls_history

    def _ai_prepare_prompt_values(self, record):
        action_prompt, context_fields = super()._ai_prepare_prompt_values(record)

        if (
            self.ai_autosort_folder_id
            and record._name == 'documents.document'
            and self.ai_autosort_folder_id == record.folder_id
        ):
            # that prompt on the document and not on the folder
            folder_prompt, folder_context_fields, target_folders = parse_ai_prompt_values(
                self.env,
                # sudo: ai_sort_prompt has group system
                record.folder_id.sudo().ai_sort_prompt,
                "documents.document",
            )
            context_fields |= folder_context_fields
            action_prompt += f"\n{folder_prompt}"
            action_prompt += "\n" + _("You can move the document in one of those folders:")
            action_prompt += "\n" + json.dumps(target_folders, ensure_ascii=False, indent=2)

        return action_prompt, context_fields
