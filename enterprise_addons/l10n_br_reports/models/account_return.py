from odoo import models


class AccountReturn(models.Model):
    _inherit = 'account.return'

    def _get_vat_closing_entry_additional_domain(self):
        # EXTENDS account_reports
        domain = super()._get_vat_closing_entry_additional_domain()
        if self.type_id.country_id.code == 'BR':
            # Brazil files one return per tax, all sharing the country's taxes, so each
            # closing must be restricted to the tags of its own report's lines.
            tax_tags = self.type_id.report_id.line_ids.expression_ids._get_matching_tags()
            domain.append(('tax_tag_ids', 'in', tax_tags.ids))
        return domain
