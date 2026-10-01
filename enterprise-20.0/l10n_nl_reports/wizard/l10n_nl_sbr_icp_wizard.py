import json

from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import api, models
from odoo.tools.misc import format_date

from odoo.addons.l10n_nl_reports.tools.iap_tooling import is_test_mode


class L10n_Nl_ReportsSbrIcpWizard(models.TransientModel):
    _name = 'l10n_nl_reports.sbr.icp.wizard'
    _inherit = ['l10n_nl_reports.sbr.tax.report.wizard']
    _description = 'L10n NL Intra-Communautaire Prestaties for SBR Wizard'

    @api.depends('date_to', 'date_from')
    def _compute_sending_conditions(self):
        # OVERRIDE
        for wizard in self:
            wizard.can_report_be_sent = (
                is_test_mode(wizard.env)
                or (
                    wizard.env.company.tax_lock_date
                    and wizard.env.company.tax_lock_date >= wizard.date_to
                    and (
                        not wizard.env.company.l10n_nl_reports_sbr_icp_last_sent_date_to
                        or wizard.date_from > wizard.env.company.l10n_nl_reports_sbr_icp_last_sent_date_to
                        or wizard.date_to < wizard.env.company.l10n_nl_reports_sbr_icp_last_sent_date_to + relativedelta(months=1)
                    )
                )
            )

    def action_download_xbrl_file(self):
        options = self.env.context['options']
        options['codes_values'] = self._generate_general_codes_values(options)
        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'model': self.env.context.get('model'),
                'options': json.dumps(options),
                'file_generator': 'export_icp_report_to_xbrl',
            }
        }

    def send_xbrl(self):
        # Send directly with a personal certificate, otherwise through the IAP group certificate.
        options = self.env.context['options']
        is_test = is_test_mode(self.env)
        icp_report_options = self.env.ref('l10n_nl_reports.dutch_icp_report').get_options(previous_options=options)
        account_return = self.env['account.return']._get_return_from_report_options(icp_report_options)
        account_return._proceed_with_submission()
        options['codes_values'] = self._generate_general_codes_values(options)
        xbrl_data = self.env['l10n_nl_reports.ec.sales.report.handler'].export_icp_report_to_xbrl(options)
        report_file = xbrl_data['file_content']

        certificate, private_key = self.env.company.sudo()._l10n_nl_get_certificate_and_key_bytes()
        if certificate and private_key:
            response = self._send_signed_xbrl_through_iap('ec_sales_list', report_file, self._get_sbr_identifier(options), certificate, private_key)
        else:
            response = self._call_iap_proxy(
                '/api/l10n_nl_reports/1/sign_and_send_xbrl',
                self._get_iap_common_params('ec_sales_list', report_file, self._get_sbr_identifier(options)),
            )
        kenmerk = response.get('kenmerk')
        access_token = response.get('access_token')
        can_track_status = bool(kenmerk and access_token)
        can_post_status = bool(account_return and can_track_status)

        if not is_test:
            self.env.company.sudo().l10n_nl_reports_sbr_icp_last_sent_date_to = self.date_to

        filename = f'icp_report_{self.date_to.year}_{self.date_to.month}.xbrl'
        message_data = {
            'subject': self.env._("ICP report sent"),
            'body': self.env._(
                "The ICP report from %(date_from)s to %(date_to)s was sent to %(environment)s.%(newline)s"
                "%(status_message)s%(newline)s"
                "%(discussion_id)s",
                date_from=format_date(self.env, self.date_from),
                date_to=format_date(self.env, self.date_to),
                environment=self.env._("Digipoort pre-production") if is_test else self.env._("Digipoort"),
                status_message=self.env._("We will post its processing status in this chatter once received.") if can_post_status else self.env._("Status polling is unavailable because no discussion ID was returned."),
                discussion_id=self.env._("Discussion ID: %(id)s", id=kenmerk) if can_track_status else self.env._("Discussion ID unavailable."),
                newline=Markup("<br>"),
            ),
            'attachments': [(filename, report_file)],
        }
        self.env['l10n_nl_reports.sbr.status.service']._process_messages_and_statuses(
            account_return, message_data, 'pending', subscribe=True,
        )

        if can_track_status:
            self._additional_processing(options, kenmerk, access_token, account_return)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': self.env._("Sending your report"),
                'type': 'success',
                'message': (
                    self.env._("Your test ICP report has been sent to Digipoort pre-production.")
                    if is_test
                    else (
                        self.env._("Your ICP report is being sent to Digipoort. Check its status in the account return's chatter.")
                        if can_post_status
                        else self.env._("Your ICP report has been sent to Digipoort.")
                    )
                ),
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
