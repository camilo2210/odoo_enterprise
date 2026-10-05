from odoo import models, fields


class L10n_SkGenerateAnnualStatementsReport(models.TransientModel):
    """
    This wizard is used to help generate the xml for the Balance Sheet and P&L report for Slovakia.
    """
    _name = 'l10n_sk.generate.annual.statements.report'
    _description = 'Generate Annual Statement'

    xml_bin = fields.Binary()
    type_of_closing = fields.Selection([('regular', "Regular"), ('extraordinary', "Extraordinary"), ('interim', "Interim")], required=True, default='regular')
    accounting_unit_size = fields.Selection([('small', "Small"), ('large', "Large")])
    options = fields.Json()

    def get_xml(self):
        self.xml_bin = self.env['l10n_sk.annual.statements.report.handler']._build_xml(self.options, self.type_of_closing, self.accounting_unit_size)
        return {
            'name': 'XML Report',
            'type': 'ir.actions.act_url',
            "url": f"/web/content/l10n_sk.generate.annual.statements.report/{self.id}/xml_bin?download=true&filename=UZPODv14.xml",
            'target': 'download',
        }
