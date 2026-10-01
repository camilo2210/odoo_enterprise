from odoo import _, api, models
from odoo.tools.translate import LazyTranslate


_lt = LazyTranslate(__name__)


class AccountReturnType(models.Model):
    _inherit = 'account.return.type'

    @api.depends('report_id')
    def _compute_report_return_type(self):
        # EXTENDS account_reports
        # In Spain, only the mod303 (tax report), mod111 and mod115 (withholdings) should generate a tax closing entry.
        # Other reports (347, 349, 390...) are for information purposes only.
        # Ideally, these other reports would not inherit from generic_tax_report--> to be implemented after v19
        super()._compute_report_return_type()

        no_closing_es_report_xmlids = (
            'l10n_es_reports.es_mod390_tax_return_type',
            'l10n_es_reports.es_mod349_tax_return_type',
            'l10n_es_reports.es_mod347_tax_return_type',
            'l10n_es_reports.es_mod130_tax_return_type',
        )
        external_id_per_type = self.get_external_id()
        for record in self:
            if external_id_per_type.get(record.id) in no_closing_es_report_xmlids:
                record.is_tax_return_type = False


class AccountReturn(models.Model):
    _inherit = 'account.return'

    def _prepare_submission(self):
        # EXTENDS account_reports
        mod_number = self._l10n_es_get_report_modelo_number()
        if mod_number:
            return self.env[f'l10n_es_reports.mod{mod_number}.submission.wizard']._open_submission_wizard(self)
        return super()._prepare_submission()

    def _get_vat_closing_entry_additional_domain(self):
        # EXTENDS account_reports
        domain = super()._get_vat_closing_entry_additional_domain()
        mod_number = self._l10n_es_get_report_modelo_number()
        if mod_number in (111, 115, 303):
            mod_tags = self.env.ref(f'l10n_es.mod_{mod_number}').line_ids.expression_ids._get_matching_tags()
            domain.append(('tax_tag_ids', 'in', mod_tags.ids))
        return domain

    def _l10n_es_get_report_modelo_number(self):
        self.ensure_one()
        if 'l10n_es_reports' in self.type_external_id:
            xmlid_to_modelo = {
                "l10n_es_reports.es_mod111_tax_return_type": 111,
                "l10n_es_reports.es_mod115_tax_return_type": 115,
                "l10n_es_reports.es_mod130_tax_return_type": 130,
                "l10n_es_reports.es_mod303_tax_return_type": 303,
                "l10n_es_reports.es_mod347_tax_return_type": 347,
                "l10n_es_reports.es_mod349_tax_return_type": 349,
                "l10n_es_reports.es_mod390_tax_return_type": 390,
            }
            return xmlid_to_modelo.get(self.type_external_id, None)
        return None

    def _check_suite_common_ec_sales_list(self, check_codes_to_ignore):
        # OVERRIDES account_reports
        if self._l10n_es_get_report_modelo_number() != 349:
            return super()._check_suite_common_ec_sales_list(check_codes_to_ignore)

        checks = []

        if 'goods_service_classification' not in check_codes_to_ignore or 'reverse_charge_mentioned' not in check_codes_to_ignore:
            options = self._get_closing_report_options()

            is_using_taxes = 'ec_sales_taxes_to_include' in options

            if is_using_taxes:
                ec_sales_tax_or_tag_domain = ('tax_ids', 'in', options.get('ec_sales_taxes_to_include', []))
            else:
                tax_tag_ids = list({
                    tag
                    for sale_type in options['sales_report_operation_types'].values()
                    for tag in sale_type['tax_tag_ids']
                })
                ec_sales_tax_or_tag_domain = ('tax_tag_ids', 'in', tax_tag_ids)

            ec_sales_aml_domain = [
                *self.type_id.report_id._get_options_domain(options, 'strict_range'),
                ec_sales_tax_or_tag_domain,
            ]

            if 'goods_service_classification' not in check_codes_to_ignore:
                checks.append({
                    'name': _lt("Goods and services classification"),
                    'message': _lt("Review the tax code and ensure each transaction is correctly classified as a supply of goods or services."),
                    'code': 'goods_service_classification',
                    'result': 'todo',
                    'action': {
                        'type': 'ir.actions.act_window',
                        'name': _("Journal Items"),
                        'res_model': 'account.move.line',
                        'domain': ec_sales_aml_domain,
                        'views': [(False, 'list')],
                    },
                })

            if 'reverse_charge_mentioned' not in check_codes_to_ignore:
                checks.append({
                    'name': _lt("Reverse charge mention"),
                    'message': _lt('Make sure the "Reverse Charge" mention appears on all invoices.'),
                    'code': 'reverse_charge_mentioned',
                    'result': 'todo',
                    'action': {
                        'type': 'ir.actions.act_window',
                        'name': _("Invoices"),
                        'res_model': 'account.move',
                        'domain': [('line_ids', 'any', ec_sales_aml_domain)],
                        'views': [(False, 'list'), (False, 'form')],
                    },
                })

        self._generic_vies_vat_check(check_codes_to_ignore, checks)

        return checks
