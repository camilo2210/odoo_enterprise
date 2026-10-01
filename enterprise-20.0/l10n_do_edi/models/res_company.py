from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_do_edi_web_service_env = fields.Selection(
        string="Web Service Environment",
        required=True,
        selection=[
            ('demo', 'Demo'),
            ('test', 'Test'),
            ('production', 'Production'),
        ],
        default='demo',
        groups='base.group_system',
    )
    l10n_do_edi_username = fields.Char("Infile WS Username", groups='base.group_system')
    l10n_do_edi_password = fields.Char("Infile WS Password", groups='base.group_system')
    l10n_do_edi_key = fields.Char("Infile WS Key", groups='base.group_system')
    l10n_do_edi_llave = fields.Char("Infile Llave", groups='base.group_system')

    def _localization_use_documents(self):
        self.ensure_one()
        return self.chart_template == 'do' or self.account_fiscal_country_id.code == "DO" or super()._localization_use_documents()
