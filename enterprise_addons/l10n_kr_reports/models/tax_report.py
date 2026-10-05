# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, models
from odoo.addons.web.controllers.utils import clean_action


class L10nKrTaxReportHandler(models.AbstractModel):
    _name = 'l10n_kr.tax.report.handler'
    _inherit = ['account.tax.report.handler']
    _description = "Korean Tax Report Custom Handler"

    def _l10n_kr_get_missing_issuance_type_domain(self, report, options):
        """ Domain of the invoices and bills reported in this period whose proof of issuance
            (발행 증빙) is not set, and that can hence not be dispatched to the right report box.
        """
        domain = [
            ('company_id', 'in', report.get_report_company_ids(options)),
            ('journal_id.type', 'in', ('sale', 'purchase')),
            ('l10n_kr_issuance_type', '=', False),
            ('date', '>=', options['date']['date_from']),
            ('date', '<=', options['date']['date_to']),
        ]
        if options.get('all_entries'):
            domain.append(('state', '!=', 'cancel'))
        else:
            domain.append(('state', '=', 'posted'))
        return domain

    def _customize_warnings(self, report, options, all_column_groups_expression_totals, warnings):
        # EXTENDS 'account.tax.report.handler'
        super()._customize_warnings(report, options, all_column_groups_expression_totals, warnings)

        if warnings is None:
            return

        moves_count = self.env['account.move'].search_count(
            self._l10n_kr_get_missing_issuance_type_domain(report, options),
        )
        if moves_count:
            warnings['l10n_kr_reports.tax_report_warning_missing_issuance_type'] = {
                'count': moves_count,
                'alert_type': 'warning',
            }

    def action_l10n_kr_open_missing_issuance_type_moves(self, options, params=None):
        """ Open the invoices and bills of the period whose proof of issuance is not set. """
        report = self.env['account.report'].browse(options['report_id'])
        action = clean_action(
            self.env['ir.actions.actions']._for_xml_id('account.action_move_journal_line'),
            env=self.env,
        )
        action['name'] = _("Missing Proof of Issuance")
        action['domain'] = self._l10n_kr_get_missing_issuance_type_domain(report, options)
        # Overwrite the context to avoid the default filtering on 'misc' journals
        action['context'] = {}
        return action
