from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_be_soda_use_analytic = fields.Boolean(string="Analytic Mapping", related='company_id.l10n_be_soda_use_analytic', readonly=False)
    l10n_be_soda_analytic_plan = fields.Many2one(string="Analytic Plan", related='company_id.l10n_be_soda_analytic_plan', readonly=False)

    def l10n_be_soda_open_soda_mapping(self):
        wizard = self.env['soda.import.wizard'].create({
            'soda_files': {},
            'company_id': self.env.company.id,
        })
        return {
            'name': self.env._('Account Mapping'),
            'view_id': self.env.ref('l10n_be_soda.soda_import_wizard_view_form').id,
            'res_model': 'soda.import.wizard',
            'res_id': wizard.id,
            'context': {**self.env.context, 'soda_mapping_save_only': True},
            'type': 'ir.actions.act_window',
            'views': [(False, 'form')],
            'view_mode': 'form',
            'target': 'new',
        }
