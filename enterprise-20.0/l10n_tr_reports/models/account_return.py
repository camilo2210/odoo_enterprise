from odoo import models


class AccountReturn(models.Model):
    _inherit = 'account.return'

    def _get_vat_closing_entry_additional_domain(self):
        domain = super()._get_vat_closing_entry_additional_domain()
        if self.type_external_id in ('l10n_tr_reports.tr_stamp_tax_return_type', 'l10n_tr_reports.tr_tax_return_type'):
            tax_tags = self.type_id.report_id.line_ids.expression_ids._get_matching_tags()
            domain.append(('tax_tag_ids', 'in', tax_tags.ids))
        return domain
