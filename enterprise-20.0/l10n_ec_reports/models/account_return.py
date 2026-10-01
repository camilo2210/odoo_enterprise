from odoo import models


class AccountReturn(models.Model):
    _inherit = 'account.return'

    def _get_vat_closing_entry_additional_domain(self):
        # EXTENDS account_reports
        domain = super()._get_vat_closing_entry_additional_domain()
        vat_return_type = 'l10n_ec_reports.ec_104_tax_return_type'
        withhold_return_type = 'l10n_ec_reports.ec_104_withhold_tax_return_type'
        return_types = (
            'l10n_ec_reports.ec_103_tax_return_type',
            vat_return_type,
            withhold_return_type,
        )
        if self.type_external_id in return_types:
            tax_tags = self.type_id.report_id.line_ids.expression_ids._get_matching_tags()
            if self.type_external_id in (vat_return_type, withhold_return_type):
                # The VAT and the VAT withheld at source share the 104 but are settled on
                # different accounts, so each return only closes the tags of its own lines.
                withhold_lines = self.type_id.report_id.line_ids.filtered(lambda line: line.code in ('c609', 'c721', 'c723', 'c725', 'c727', 'c729', 'c731'))
                withhold_tags = withhold_lines.expression_ids._get_matching_tags()
                if self.type_external_id == withhold_return_type:
                    tax_tags = withhold_tags
                else:
                    tax_tags -= withhold_tags
            domain.append(('tax_tag_ids', 'in', tax_tags.ids))
        return domain
