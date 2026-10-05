from odoo import models


class AccountReturn(models.Model):
    _inherit = 'account.return'

    def _get_vat_closing_entry_additional_domain(self):
        # EXTENDS account_reports
        domain = super()._get_vat_closing_entry_additional_domain()
        return_types = [
            'l10n_ca_reports.ca_gsthst_tax_return_type',
            'l10n_ca_reports.ca_pst_bc_tax_return_type',
            'l10n_ca_reports.ca_pst_mb_tax_return_type',
            'l10n_ca_reports.ca_pst_sk_tax_return_type',
        ]
        if self.type_external_id in return_types:
            tax_tags = self.type_id.report_id.line_ids.expression_ids._get_matching_tags()
            domain.append(('tax_tag_ids', 'in', tax_tags.ids))
        elif self.type_external_id == 'l10n_ca_reports.ca_qst_tax_return_type':
            # The FPZ-500 has a GST/HST column and a QST one; the federal side is settled by
            # the GST/HST return, so this one only closes what belongs to the QST column.
            qst_expressions = self.type_id.report_id.line_ids.expression_ids.filtered(
                lambda expression: expression.label == 'qst'
            )
            domain.append(('tax_tag_ids', 'in', qst_expressions._get_matching_tags().ids))
        return domain
