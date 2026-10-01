# models/res_company.py
from odoo import models, SUPERUSER_ID


class ResCompany(models.Model):
    _inherit = "res.company"

    def _generate_employee_documents_main_folders(self):
        """Generate employee document folders and embed the Sign template creation action."""
        super()._generate_employee_documents_main_folders()
        if sign_action := self.env.ref(
            'documents_sign.ir_actions_server_create_sign_template_direct',
            raise_if_not_found=False
        ):
            self.documents_employee_folder_id.with_user(SUPERUSER_ID)._embed_action(sign_action.id)
