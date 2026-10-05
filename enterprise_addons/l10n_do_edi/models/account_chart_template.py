from odoo import models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('do', 'res.company')
    def _get_do_edi_res_company(self):
        return {
            self.env.company.id: {
                'display_invoice_amount_total_words': True,
            },
        }

    @template('do', 'account.tax')
    def _get_do_taxes(self):
        return self._parse_csv('do', 'account.tax', module='l10n_do_edi')

    @template(model='account.move', demo=True)
    def _get_demo_data_move(self, template_code):
        """
        Override
        - _localization_use_documents was overridden to be true for l10n_do_edi
        but _is_manual_document_number was not overridden, thus using default behavior
        - Default demo data creates default journals such as purchase for DO company
        - Purchase journal has use_documents = True, which will throw an error to manually set the document number
        when _check_l10n_latam_documents is called
        - Similar to l10n_br
        """
        move_data = super()._get_demo_data_move(template_code)
        if template_code == 'do':
            number = 0
            for move in move_data.values():
                if move['move_type'] in ('in_invoice', 'in_refund'):
                    move['l10n_latam_document_number'] = f'{number:08d}'
                    number += 1
        return move_data
