from odoo import models


class AccountReturn(models.Model):
    _inherit = 'account.return'

    def _get_vat_closing_entry_additional_domain(self):
        # EXTENDS account_reports
        domain = super()._get_vat_closing_entry_additional_domain()
        vat_return_type = 'l10n_ph_reports.ph_tax_return_type'
        wht_return_type = 'l10n_ph_reports.ph_wht_tax_return_type'
        if self.type_external_id in (vat_return_type, wht_return_type):
            # The VAT and the withholding tax share the 2550Q but are settled on different
            # accounts, so each return only closes the tags of its own lines of that report.
            withholding_lines = (
                self.env.ref('l10n_ph.l10n_ph_2550Q_2550q_16', raise_if_not_found=False)
                | self.env.ref('l10n_ph.l10n_ph_2550Q_2550q_61', raise_if_not_found=False)
            )
            withholding_tags = withholding_lines.expression_ids._get_matching_tags()
            if self.type_external_id == wht_return_type:
                domain.append(('tax_tag_ids', 'in', withholding_tags.ids))
            else:
                domain.append(('tax_tag_ids', 'not in', withholding_tags.ids))
        return domain
