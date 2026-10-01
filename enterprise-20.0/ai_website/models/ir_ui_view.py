from odoo import models
from typing import override


class IrUiView(models.Model):
    _inherit = 'ir.ui.view'

    @override
    def _get_allowed_root_attrs(self):
        return super()._get_allowed_root_attrs() + ['data-contains-ai-content']
