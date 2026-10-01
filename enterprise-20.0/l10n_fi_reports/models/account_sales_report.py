import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class FinlandECSalesReportCustomHandler(models.AbstractModel):
    _name = 'l10n_fi_reports.ec.sales.report.handler'
    _inherit = 'account.ec.sales.with.tags.report.handler'
    _description = 'Finland EC Sales Report Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        fi_tax_tags = self._get_ec_sales_tax_tags()
        options.update({
            'sales_report_operation_types': {
                'goods': {
                    'tax_tag_ids': fi_tax_tags['goods'],
                },
                'services': {
                    'tax_tag_ids': fi_tax_tags['services'],
                },
                'triangular': {
                    'tax_tag_ids': fi_tax_tags['triangular'],
                },
            },
        })

        super()._custom_options_initializer(report, options, previous_options)

        options['buttons'].append({
            'name': _("Generate VSRALVYV"),
            'sequence': 150,
            'action': 'export_file',
            'action_param': 'l10n_fi_export_ec_sales_list_report',
            'file_export_type': _('TXT'),
        })

    @api.model
    def _get_ec_sales_tax_tags(self):
        tax_report_goods_eu_tag = self.env.ref('l10n_fi.tax_report_base_sales_goods_eu_tax_tag')
        tax_report_services_eu_tag = self.env.ref('l10n_fi.tax_report_base_sales_service_eu_tag')
        tax_report_triangular_eu_tag = self.env.ref('l10n_fi.tax_report_base_triangular_eu_tax_tag')

        return {
            'goods': tax_report_goods_eu_tag._get_matching_tags().ids,
            'services': tax_report_services_eu_tag._get_matching_tags().ids,
            'triangular': tax_report_triangular_eu_tag._get_matching_tags().ids,
        }

    @api.model
    def l10n_fi_export_ec_sales_list_report(self, options):
        if options['date']['period_type'] != 'month':
            raise UserError(_("The declaration should be month by month. Please select only a month period."))
        if not self.env.company.partner_id._get_additional_identifier('FI_EN'):
            raise UserError(_("Business ID is needed on your current company to export VSRALVYV."))

        generated_time = fields.Datetime.now()
        timestamp_date = generated_time.strftime('%d%m%Y')
        timestamp_time = generated_time.strftime('%H%M%S')
        file_content = self.env['ir.actions.report']._render_qweb_text(
            report_ref='l10n_fi_reports.action_generate_ec_sales_list_report_export',
            docids=[options['report_id']],
            data={
                'timestamp': f'{timestamp_date}{timestamp_time}',
                'options': options,
            },
        )
        return {
            'file_name': f'V_{timestamp_date}_{timestamp_time}_VSRALVYV.txt',
            'file_content': file_content[0],
            'file_type': 'txt',
        }
