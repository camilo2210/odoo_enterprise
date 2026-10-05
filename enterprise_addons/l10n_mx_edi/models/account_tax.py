from odoo import api, models


class AccountTax(models.Model):
    _inherit = "account.tax"

    @api.model
    def _l10n_mx_edi_is_generic_local_tax(self, tax):
        generic_local_tax = self.env['account.chart.template'].with_company(tax.company_id)\
            .ref(f'l10n_mx_edi_tax_local_{tax.type_tax_use}', raise_if_not_found=False)
        return tax.l10n_mx_tax_type == 'local' and tax == generic_local_tax

    def _prepare_base_line_for_taxes_computation(self, record, **kwargs):
        # EXTENDS 'account'
        results = super()._prepare_base_line_for_taxes_computation(record, **kwargs)
        if (
            isinstance(record, models.Model)
            and record._name == 'account.move.line'
            and record.tax_ids and all(self._l10n_mx_edi_is_generic_local_tax(tax) for tax in record.tax_ids)
        ):
            results['manual_tax_line_name'] = record.name  # Use invoice line name instead of the generic tax one
            results['_l10n_mx_generic_local_tax_line'] = True
        return results

    def _prepare_tax_line_for_taxes_computation(self, record, **kwargs):
        # EXTENDS 'account'
        results = super()._prepare_tax_line_for_taxes_computation(record, **kwargs)
        if (
            isinstance(record, models.Model)
            and record._name == 'account.move.line'
            and self._l10n_mx_edi_is_generic_local_tax(record.tax_line_id)
        ):
            results['name'] = record.name
            results['_l10n_mx_generic_local_tax_line'] = True
        return results

    def _prepare_base_line_tax_repartition_grouping_key(self, base_line, base_line_grouping_key, tax_data, tax_rep_data):
        # EXTENDS 'account'
        results = super()._prepare_base_line_tax_repartition_grouping_key(base_line, base_line_grouping_key, tax_data, tax_rep_data)
        if base_line.get('_l10n_mx_generic_local_tax_line'):
            results['name'] = base_line['manual_tax_line_name']
        return results

    def _prepare_tax_line_repartition_grouping_key(self, tax_line):
        # EXTENDS 'account'
        results = super()._prepare_tax_line_repartition_grouping_key(tax_line)
        if tax_line.get('_l10n_mx_generic_local_tax_line'):
            results['name'] = tax_line['name']
        return results

    def _l10n_mx_edi_import_retrieve_tax_from_l10n_mx_identifiers(self, tax_values):
        if not tax_values.get('l10n_mx_factor_type') and not tax_values.get('l10n_mx_tax_type'):
            return

        domain = []
        if factor_type := tax_values.get('l10n_mx_factor_type'):
            domain.append(('l10n_mx_factor_type', '=', factor_type))
        if tax_type := tax_values.get('l10n_mx_tax_type'):
            domain.append(('l10n_mx_tax_type', '=', tax_type))

        if domain:
            return {'criteria': [{'domain': domain}]}
