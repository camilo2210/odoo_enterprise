import json
import logging

from markupsafe import Markup
from odoo import api, fields, models
from odoo.addons.iap.tools import iap_tools
from odoo.exceptions import UserError
from odoo.tools import LazyTranslate, _

_lt = LazyTranslate(__name__)
_logger = logging.getLogger(__name__)
ENDPOINT = "https://l10n-fr-aspone.api.odoo.com"
TEST_ENDPOINT = "https://l10n-fr-aspone.test.odoo.com"

# Allows to translate the errors returned by IAP
ERROR_CODE_TO_MSG = {
    'api_error': _lt("An unexpected error occured"),
    'aspone_credentials_not_configured': _lt("Aspone credentials are not configured."),
    'aspone_sso_account_tittle_error': _lt("Subscriber title must be 'MS' or 'MR'."),
    'aspone_sso_missing_field': _lt("One or more fields are missing."),
    'dbuuid_not_exist': _lt("Your database uuid does not exist"),
    'error_subscription': _lt("An error has occurred when trying to verify your subscription."),
    'insee_code_not_found': _lt("The INSEE code could not be found for the given commune / country."),
    'invalid_model_for_insee_lookup': _lt("The model provided for the INSEE lookup is not valid."),  # We can probably remove this one as it shouldn't happen functionally.
    'invalid_xml_root': _lt("The root of your XML file is invalid."),
    'invalid_xml_syntax': _lt("The syntax of your XML file is invalid."),
    'missing_debtor_identifier': _lt("The debtor's identifier is missing."),
    'missing_test_attribute': _lt("The test attribute is missing in your XML file."),
    'missing_writer_siret': _lt("Your SIRET number is missing."),
    'network_error': _lt("A network error occurred while connecting to ASPOne."),
    'no_interchanges_found': _lt("No interchange was found for this deposit."),
    'not_active_db': _lt("Your database is not yet activated."),
    'not_enterprise': _lt("You do not have an Odoo enterprise subscription."),
    'not_prod_env': _lt("Your database is not used for a production environment."),
    'unauthorized_access': _lt("Access denied."),
    'unknown_declaration': _lt("This declaration is unknown from Odoo."),
    'unknown_deposit': _lt("This deposit is unknown from Odoo."),
    'unknown_procedure': _lt("Wrong procedure value provided."),
    'xml_validation_error': _lt("There was an unexpected error during the validation of the XML file."),
}


class AccountReportAsyncDocument(models.Model):
    _name = 'account.report.async.document'
    _description = "Account Report Async Document"

    name = fields.Char()
    account_report_async_export_id = fields.Many2one('account.report.async.export')
    attachment = fields.Binary()
    attachment_name = fields.Char()
    deposit_uid = fields.Char()  # ASPOne "Interchange" identifier
    declaration_uid = fields.Char()  # ASPOne identifier (an interchange might have several declarations)
    state = fields.Selection(
        selection=[
            ('to_send', "To send"),  # nothing was sent to ASPone
            ('sent', "Sent"),  # xml sent to ASPone (via AddDocument)
            ('accepted', "Accepted"),  # GetDeclaration returned "ACCEPTED_BY_DESTINATATION"
            ('rejected', "Rejected"),  # GetDeclaration returned "REJECTED_BY_DESTINATION" OR "TRANSLATED_KO"
        ],
        default='to_send',
    )
    step_1_logs = fields.Char()
    step_2_logs = fields.Char()
    message = fields.Html(compute='_compute_message')

    @api.depends("step_1_logs", "step_2_logs", "state")
    def _compute_message(self):
        for report in self:
            full_logs = json.loads(report.step_1_logs or '[]') + json.loads(report.step_2_logs or '[]')
            msg = report._get_message(full_logs)
            if report.state == 'to_send':
                report.message = Markup("")
            elif report.state == 'accepted':
                report.message = Markup("<b>%s</b>") % _("The report has been fully processed by the recipient") + msg
            elif report.state == 'rejected':
                report.message = Markup("<b>%s</b>") % _("The report has been rejected") + msg
            else:
                report.message = Markup("<b>%s</b>") % _("Warning, the report has not been fully processed by the recipient yet") + msg

    @api.model
    def _get_message(self, logs):
        """Recursively build the message from the logs."""
        if not logs:
            return ''
        errstyle = Markup(" class='text-danger'")
        msg = [Markup("<ul>")]
        for log in logs:
            msg.append(Markup("<li{style}>{name}: {label}{details}</li>").format(
                style=errstyle if log['is_error'] else '',
                name=log['name'],
                label=log['label'],
                details=self._get_message(details) if (details := log.get('details')) else '',
            ))
        msg.append(Markup("</ul>"))
        return Markup().join(msg)

    def _process_reports_async_documents(self):
        """
        The ASPOne API returns a depositID when sending a document through `AddDocument`.
        Using this depositID, we call `getInterchangesByDepositID` to get the list of "interchanges" associated to this
        document. Each "interchange" contains 1 to n declarations (they each have a declarationID).
        The details of a declaration are then obtained by calling `getDeclarationDetails` with the declarationID.

        In this module, each document creates one interchange (deposit_uid) linked to one declaration (declaration_uid).

        The API will first process the xml: validate it, convert it to an edifact file and validate the edifact (this
        is the 1st step, using `getInterchangesByDepositID`).
        Then, it will send the edifact to the recipient, and obtain its acknowledgment (this is the 2nd step, using
        `getDeclarationDetails`).

        If the 1st step returns an error (for instance: invalid xml/edifact), the flow will be stopped, and there is
        no need to call the 2nd step. In addition, the 2nd step is only executed when the 1st was done (i.e. when it
        received a final state and was not in error).
        """
        for export in self:
            try:
                # Avoid calling the first step again if its state is already final
                first_step_state_final = False
                if export.step_1_logs:
                    first_step_state_final = any(status['is_final'] for status in json.loads(export.step_1_logs))

                # First step
                if not first_step_state_final:
                    response = export._get_interchanges_by_deposit_id()
                    step_1_logs = export._process_interchanges_response(response)
                    export.step_1_logs = json.dumps(step_1_logs)
                    if any(status['is_error'] for status in step_1_logs):
                        export.state = 'rejected'
                        export.account_report_async_export_id.return_id._message_log(body=self.env._(
                            "The document %(document_name)s was rejected by ASPOne.",
                            documentname=export.name,
                        ))
                    first_step_state_final = any(status['is_final'] for status in step_1_logs)

                # Second step
                if first_step_state_final and export.state != 'rejected' and export.declaration_uid:
                    response = export._get_declaration_details()
                    step_2_logs = export._process_declaration_response(response)

                    export.step_2_logs = json.dumps(step_2_logs)
                    if any(status['is_error'] for status in step_2_logs):
                        export.state = 'rejected'
                        export.account_report_async_export_id.return_id._message_log(body=self.env._(
                            "The document %(document_name)s was rejected by ASPOne.",
                            documentname=export.name,
                        ))
                    elif any(status['is_final'] for status in step_2_logs):
                        export.state = 'accepted'
                        export.account_report_async_export_id.return_id._message_log(body=self.env._(
                            "The document %(document_name)s was accepted by ASPOne.",
                            documentname=export.name,
                        ))
            except Exception as e:  # noqa: BLE001
                _logger.warning("Error while processing interchanges response: %s", e)

            if export.state == 'rejected':
                report_closing_entry = export.env['account.move'].search([
                    ('closing_return_id', '=', export.account_report_async_export_id.report_id.id),
                    ('date', '=', export.account_report_async_export_id.date_to),
                ])
                act_type_xmlid = 'account_reports.mail_activity_type_tax_report_error'
                report_closing_entry.activity_reschedule(
                    act_type_xmlids=[act_type_xmlid],
                    date_deadline=fields.Date.context_today(report_closing_entry)
                ) or report_closing_entry.activity_schedule(
                    act_type_xmlid=act_type_xmlid,
                    summary=_("Tax Report Error: %s", report_closing_entry.closing_return_id.name),
                )

    # ------------------------------------------------------------
    # Helper functions
    # ------------------------------------------------------------

    @api.model
    def _collect_errors_in_history(self, history, logs):
        """ The ASPOne API returns a list of events associated with the xml file sent. Each event has a status, a label,
        flags indicating the state is in error, is final, etc. A final state indicates the xml file has been approved
        by the recipient (e.g. the DGFiP) or has raised a fatal error.

        This function collects the events contained in a stateHistory ('history') into 'logs'.

        :param logs: has the following structure:
        [
            {'name': 'status_1', 'label': 'blabla', 'is_error': False, 'details': []},
            {'name': 'status_2', 'label': 'blabla', 'is_error': True, 'details': [
                {'name': 'status_2.A', 'label': 'more detailed blabla', 'is_error': True},
                {'name': 'status_2.B', 'label': 'more detailed blabla', 'is_error': True},
            ]},
        ]
        """
        log = {
            'name': history['name'],
            'label': history['label'],
            'is_error': history['type'] == 'ERROR',
            'is_final': history['final'],
            'details': [],
        }

        for detail in (history.get('details') or []):
            label = detail.get('label')
            if label_detail := detail.get('detail'):
                label += f": {label_detail}"
            sub_log = {
                'name': detail.get('name') or _("DETAIL"),
                'label': label,
                'is_error': detail['type'] == 'ERROR',
                'is_final': detail.get('final'),
            }
            log['details'].append(sub_log)

        logs.append(log)

    @api.model
    def _get_fr_webservice_answer(self, url, params):
        """ Post the request and catch known Exceptions, return the content of the response as a dict. """
        response = iap_tools.iap_jsonrpc(url, params=params, raise_user_error=True)

        if not response.get('success'):
            if response.get('error') == 'validation_error':
                error_code = response.get('message')
                msg = ERROR_CODE_TO_MSG.get(error_code) or self.env._("A validation error occurred: %(error_code)s.", error_code=error_code)
            else:
                msg = self.env._("An internal error occurred.")
            msg += self.env._(" Please try again.\nIf the error still persists please contact the support.")
            raise UserError(msg)

        return response

    @api.model
    def _is_aspone_test_mode(self):
        is_neutralized = self.env['ir.config_parameter'].sudo().get_bool('database.is_neutralized')
        aspone_mode = self.env['ir.config_parameter'].sudo().get_str('l10n_fr_reports.aspone_mode', 'prod')
        return aspone_mode.lower() == 'test' or is_neutralized

    # ------------------------------------------------------------
    # Processing the ASPOne responses
    # ------------------------------------------------------------

    def _process_interchanges_response(self, response):
        if not response['data']['interchange'].get('interchange_id'):
            raise Exception(_("Unexpected result: the response should contain an interchange."))
        interchange = response['data']['interchange']

        logs = []
        # The events are logged in reversed order (last event in 1st position)
        for history in reversed(interchange['states']):
            self._collect_errors_in_history(history, logs)
        # Get the declaration_uid, NB: it will only be available when no errors were returned at this step
        if interchange['declaration_ids'] and not self.declaration_uid:
            if len(interchange['declaration_ids']) > 1:
                # Can occur if we send a document to more than one recipient (e.g. DGFiP + OGA)
                raise Exception(_("Unexpected result: the interchange should contain at most one declarationId."))
            self.declaration_uid = interchange['declaration_ids'][0]
        return logs

    def _process_declaration_response(self, response):
        logs = []
        for history in reversed(response['data']['states']):
            self._collect_errors_in_history(history, logs)
            if history['type'] == 'ERROR':
                self.state = 'rejected'
            if history['name'] == 'ACCEPTED_BY_DESTINATION':
                self.state = 'accepted'
        return logs

    def _process_recipient_reports_response(self, response):
        attachments_vals = []
        for recipient_report in response['response']['successfullResponse']['RecipientReports']:
            for report in recipient_report['report']:
                if 'data' not in report:
                    continue
                attachments_vals.append({
                    'name': report['filename'],
                    'res_model': 'account.report.async.export',
                    'res_id': self.id,
                    'type': 'binary',
                    'raw': report['data'].replace("'", "\n").encode(),  # format the edifact file
                    'mimetype': 'application/text',
                })
        return attachments_vals

    # ------------------------------------------------------------
    # Calls to ASPOne (via IAP)
    # ------------------------------------------------------------

    def _get_aspone_endpoint(self):
        aspone_mode = self.env['ir.config_parameter'].sudo().get_str('l10n_fr_reports.aspone_mode', 'prod')
        aspone_endpoint = self.env['ir.config_parameter'].sudo().get_str('l10n_fr_reports.aspone_endpoint')
        return aspone_endpoint or TEST_ENDPOINT if aspone_mode.lower() == 'test' else ENDPOINT

    def _get_interchanges_by_deposit_id(self):
        """ First step: get the interchanges linked to a deposit_uid (possibly several interchanges per deposit). """
        db_uuid = self.env['ir.config_parameter'].sudo().get_str('database.uuid')
        endpoint = self._get_aspone_endpoint()
        return self._get_fr_webservice_answer(
            url=endpoint + "/api/l10n_fr_aspone/2/get_interchanges_by_deposit_id",
            params={'db_uuid': db_uuid, 'deposit_uid': self.deposit_uid},
        )

    def _get_declaration_details(self):
        """ Second step: get info of a single declaration/interchange. """
        db_uuid = self.env['ir.config_parameter'].sudo().get_str('database.uuid')
        endpoint = self._get_aspone_endpoint()
        return self._get_fr_webservice_answer(
            url=endpoint + "/api/l10n_fr_aspone/2/get_declaration_details",
            params={'db_uuid': db_uuid, 'declaration_uid': self.declaration_uid},
        )
