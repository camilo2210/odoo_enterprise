# Part of Odoo. See LICENSE file for full copyright and licensing details.

import ast

from odoo import fields, models


class TestModelMixinParent(models.Model):
    _name = "test.model.mixin.parent"
    _description = "Test Model Mixin Parent"
    _inherit = ["mail.alias.mixin"]

    name = fields.Char(string="Name")
    company_id = fields.Many2one("res.company")

    def _alias_get_creation_values(self):
        values = super()._alias_get_creation_values()
        values["alias_model_id"] = self.env["ir.model"]._get("documents.mixin.folder.test.model").id
        if self.id:
            values["alias_defaults"] = defaults = ast.literal_eval(self.alias_defaults or "{}")
            defaults["company_id"] = self.company_id.id
        return values
