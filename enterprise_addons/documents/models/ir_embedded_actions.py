from odoo import api, models
from odoo.fields import Domain


class IrEmbeddedActions(models.Model):
    _inherit = "ir.embedded.actions"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._check_documents_can_pin()
        return records

    def write(self, vals):
        self._check_documents_can_pin()
        ret = super().write(vals)
        self._check_documents_can_pin()
        return ret

    def _check_documents_can_pin(self):
        """Check that the current user can edit/create the embedded action."""
        to_check = self.filtered(
            lambda a: a.parent_action_id == self.env.ref("documents.document_action", raise_if_not_found=False)
            and a.parent_res_model == "documents.document"
            and a.parent_res_id
        )
        if to_check:
            folders = self.env["documents.document"].browse(to_check.mapped("parent_res_id"))
            folders.check_access("write")

    @api.model
    def _get_documents_embed_base_domain(self):
        return [
            ("parent_action_id", "=", self.env.ref("documents.document_action").id),
            ("action_id.type", "=", "ir.actions.server"),
            ("parent_res_model", "=", "documents.document"),
        ]

    @api.autovacuum
    def _gc_documents_obsolete(self):
        """Remove documents embedded actions for children actions as they can't be executed."""
        documents_executable_domain = self._get_documents_embed_base_domain()
        Documents = self.env['documents.document']
        documents_server_actions_domain_all_companies = Documents.with_context(documents_gc_actions=True)._get_embeddable_server_action_domain()
        documents_embeddable_server_action = self.env["ir.actions.server"]._search(documents_server_actions_domain_all_companies)
        documents_not_embeddable_domain = [('action_id', 'not in', documents_embeddable_server_action)]
        self.env["ir.embedded.actions"].search(
            Domain.AND([documents_executable_domain, documents_not_embeddable_domain])
        ).unlink()
