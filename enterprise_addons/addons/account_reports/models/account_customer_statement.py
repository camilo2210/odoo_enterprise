from odoo import models, _


class CustomerStatementCustomHandler(models.AbstractModel):
    _name = 'account.customer.statement.report.handler'
    _inherit = 'account.partner.ledger.report.handler'
    _description = 'Customer Statement Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options)

        options['buttons'].append({
            'name': _('Send'),
            'action': 'action_send_statements',
            'sequence': 90,
            'always_show': True,
        })
        options['custom_display_config']['css_custom_class'] += ' customer_statement'

        if self.env.ref('account_reports.pdf_export_main_customer_report', raise_if_not_found=False):
            options['custom_display_config'].setdefault('pdf_export', {})['pdf_export_main'] = 'account_reports.pdf_export_main_customer_report'

    def _get_subformulas_rules(self):
        return super()._get_subformulas_rules() | {
            'amount': {'field': 'balance', 'from_beginning': True}
        }

    def action_send_statements(self, options):
        template = self.env.ref('account_reports.email_template_customer_statement', False)
        partners = self.env['res.partner'].browse(options.get('partner_ids', []))
        return {
            'name': _("Send %s Statement", partners.name) if len(partners) == 1 else _("Send Customer Statements"),
            'type': 'ir.actions.act_window',
            'views': [[False, 'form']],
            'res_model': 'account.report.send',
            'target': 'new',
            'context': {
                'default_mail_template_id': template.id if template else False,
                'default_report_options': options,
            },
        }
