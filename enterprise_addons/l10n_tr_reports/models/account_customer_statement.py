from odoo import models


class CustomerStatementTRHandler(models.AbstractModel):
    _inherit = 'account.customer.statement.report.handler'

    def action_send_statements(self, options):
        action = super().action_send_statements(options)
        if self.env.company.account_fiscal_country_id.code == 'TR':
            template = self.env.ref(
                'l10n_tr_reports.email_template_reconciliation_letter',
                raise_if_not_found=False,
            )
            if template:
                action['context']['default_mail_template_id'] = template.id

        return action

    def _get_pdf_export_html(self, options, lines, additional_context=None, template=None):
        partner_ids = options.get('partner_ids') or []
        if (
            self.env.company.account_fiscal_country_id.code == 'TR'
            and len(partner_ids) == 1
        ):
            selected_partner = self.env['res.partner'].browse(partner_ids)
            partner_line = None
            invoice_count = 0
            for line in lines:
                if line.level == 2 and line.groupby == 'id':
                    partner_line = line
                if line.level == 4 and line.groupby is None:
                    invoice_count += 1

            invoice_total = next(
                (col.name for col in partner_line.columns if col.expression_label == 'amount'),
                ''
            ) if partner_line else ''

            additional_context.update({
                'selected_partner': selected_partner,
                'is_turkish': (
                    selected_partner.lang == 'tr_TR'
                    or self.env.user.lang == 'tr_TR'
                ),
                'invoice_count': invoice_count,
                'invoice_total': invoice_total,
            })

        return self.env['account.report'].browse(options['report_id'])._get_pdf_export_html(
            options,
            lines,
            additional_context,
            template,
        )
