from datetime import timedelta
from itertools import chain

import requests
from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import Command, fields, models
from odoo.exceptions import RedirectWarning, UserError


class AccountReturnType(models.Model):
    _inherit = 'account.return.type'

    def _generate_all_returns(self, country_code, main_company, tax_unit=None, return_types=None):
        rslt = super()._generate_all_returns(country_code, main_company, tax_unit=tax_unit, return_types=return_types)

        if country_code == 'DE' and (ec_sales_return_type := self.env.ref('l10n_de_reports.de_ec_sales_list_return_type', raise_if_not_found=False)):

            months_offset = ec_sales_return_type._get_periodicity_months_delay(main_company)
            previous_period_start, previous_period_end = ec_sales_return_type._get_period_boundaries(main_company, fields.Date.context_today(self) - relativedelta(months=months_offset))
            company_ids = self.env['account.return'].sudo()._get_company_ids(main_company, tax_unit, ec_sales_return_type.report_id)
            ec_sales_list_tags_info = self.env['l10n_de.ec.sales.report.handler']._get_ec_sales_tax_tags()
            ec_sales_list_tag_ids = list(chain(*ec_sales_list_tags_info.values()))

            need_ec_sales_list = bool(self.env['account.move.line'].search_count([
                ('tax_tag_ids', 'in', ec_sales_list_tag_ids),
                *self.env['account.move.line']._check_company_domain(company_ids.ids),
                ('date', '>=', previous_period_start),
                ('date', '<=', previous_period_end),
            ], limit=1))

            if need_ec_sales_list:
                ec_sales_return_type._try_create_return_for_period(previous_period_start, main_company, tax_unit)

        return rslt


class AccountReturn(models.Model):
    _inherit = 'account.return'

    l10n_de_elster_payload_attachment_id = fields.Many2one(comodel_name='ir.attachment')

    def _evaluate_deadline(self, company, return_type, return_type_external_id, date_from, date_to):
        months_per_period = return_type._get_periodicity_months_delay(company)
        if return_type_external_id == 'l10n_de_reports.de_tax_return_type':
            return date_to + timedelta(days=10)
        if return_type_external_id == 'l10n_de_reports.de_ec_sales_list_return_type' and months_per_period in (1, 3):
            return date_to + timedelta(days=25)

        return super()._evaluate_deadline(company, return_type, return_type_external_id, date_from, date_to)

    def _proceed_with_submission(self, options_to_inject=None):
        res = super()._proceed_with_submission(options_to_inject)
        if self.type_external_id == 'l10n_de_reports.de_tax_return_type':
            self._l10n_de_reports_action_submit()
        return res

    def _reset_common(self):
        super()._reset_common()
        self.l10n_de_elster_payload_attachment_id = False

    def _link_l10n_de_elster_payload_attachment_id(self, data):
        self.l10n_de_elster_payload_attachment_id = self.env['ir.attachment'].sudo().create({
            'name': data['file_name'],
            'mimetype': 'application/xml',
            'raw': data['file_content'],
            'res_model': self._name,
            'res_id': self.id,
        })
        self.message_post(
            body=self.env._("The tax report's XML has been attached. You can review it before submission."),
            attachment_ids=self.l10n_de_elster_payload_attachment_id.ids,
        )

    def _generate_locking_attachments(self, options):
        super()._generate_locking_attachments(options)
        if self.type_external_id == 'l10n_de_reports.de_tax_return_type':
            self._link_l10n_de_elster_payload_attachment_id(self.type_id.report_id.dispatch_report_action(options, 'export_tax_report_to_xml'))

    def _l10n_de_reports_get_payload_xml(self, report, options):
        if not self.l10n_de_elster_payload_attachment_id:
            data = self.env[report.custom_handler_model_name].export_tax_report_to_xml(options)
            self._link_l10n_de_elster_payload_attachment_id(data)
        return self.l10n_de_elster_payload_attachment_id.raw.decode('iso-8859-1')

    def _l10n_de_reports_get_company_tax_number(self, company):
        if not (tax_number := company.get_l10n_de_stnr_national()):
            raise RedirectWarning(
                self.env._("Your company's must have a SteuerNummer. Please configure it before submitting to ELSTER."),
                company._get_records_action(),
                self.env._("Configure your company"),
            )
        return tax_number

    def _l10n_de_reports_action_submit(self):
        self.ensure_one()

        report = self.type_id.report_id
        options = report.get_options({'date': {'date_from': str(self.date_from), 'date_to': str(self.date_to)}})
        company = report._get_sender_company_for_export(options)
        payload_xml = self._l10n_de_reports_get_payload_xml(report, options)
        config_params = self.env['ir.config_parameter'].sudo()
        db_uuid = config_params.get_str('database.uuid')
        send_mode = config_params.get_str('l10n_de_reports.elster_proxy_mode', 'prod')

        payload = {
            'report_content':  payload_xml,
            'send_mode': send_mode,
            'tax_number': self._l10n_de_reports_get_company_tax_number(company),
        }

        proxy_url = config_params.get_str(
            'l10n_de_reports.elster_proxy_url',
            'https://l10n-de-elster.api.odoo.com',
        ).rstrip('/')

        try:
            response = requests.post(
                url=f'{proxy_url}/api/l10n_de_elster/1/submit',
                params={'db_uuid': db_uuid},
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException:
            raise UserError(self.env._("Submission Failed, Please try again later"))
        result = response.json()
        self._l10n_de_reports_process_response(result)

    def _l10n_de_reports_process_response(self, result):

        if 'error' in result:
            error = result['error']
            msg = self.env._("Submission failed with error code: %s", result['error']['eric_code'])
            if error_list := [validation_error.get('message', '') for validation_error in error.get('validation_errors', [])]:
                msg += self.env._("\n\nDetails:\n") + "\n".join(error_list)
            msg += self.env._("\n\nFor complete error code reference, check out https://docs.rs/eric-sdk/latest/eric_sdk/enum.ErrorCode.html.")
            raise UserError(msg)

        messages = [Markup("<strong>%s</strong>") % self.env._("Successfully submitted to Elster.")]
        if ticket := result['transfer_ticket']:
            messages.append(Markup("<br/>%s") % self.env._("Transfer Ticket: %s", ticket))
        if hints := result.get('hints'):
            messages.append(Markup("<br/><em>%s</em>") % self.env._("Hints:"))
            hint_items = [Markup("<li>[%s] %s</li>") % (h.get('field', ''), h.get('message', '')) for h in hints]
            messages.append(Markup("<ul>%s</ul>") % Markup("").join(hint_items))

        period = f'{self.date_to.year}_{self.date_to.month}'

        if pdf_b64 := result['pdf_confirmation']:
            attachment = self.env['ir.attachment'].sudo().create({
                'name': f'ELSTER_Uebertragungsprotokoll_{period}.pdf',
                'raw': pdf_b64,
                'type': 'binary',
                'res_model': self._name,
                'res_id': self.id,
            })
            self.attachment_ids = [Command.link(attachment.id)]

        self.message_post(body=Markup("").join(messages))
