from odoo import models


class IrModuleModule(models.Model):
    _inherit = "ir.module.module"

    def _load_module_terms(self, modules, langs, overwrite=False):
        super()._load_module_terms(modules, langs, overwrite=overwrite)
        self.env['mail.template']._sync_dian_mail_templates_translations(langs)
