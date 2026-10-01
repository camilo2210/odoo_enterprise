from odoo import models


class AccountReturn(models.Model):
    _inherit = 'account.return'

    def _get_vat_closing_entry_additional_domain(self):
        # EXTENDS account_reports
        domain = super()._get_vat_closing_entry_additional_domain()
        return_types = [
            'l10n_tw_reports.tw_tax_return_type',
            'l10n_tw_reports.tw_403_tax_return_type',
            'l10n_tw_reports.tw_404_tax_return_type',
        ]
        if self.type_external_id in return_types:
            tax_tags = self.type_id.report_id.line_ids.expression_ids._get_matching_tags()
            domain.append(('tax_tag_ids', 'in', tax_tags.ids))
        return domain
