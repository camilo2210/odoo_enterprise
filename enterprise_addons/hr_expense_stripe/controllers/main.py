import base64
import logging
import traceback

from werkzeug.utils import secure_filename

from odoo import SUPERUSER_ID, api
from odoo.exceptions import MissingError, UserError, ValidationError
from odoo.http import Controller, request, route
from odoo.tools.safe_eval import time

from odoo.addons.hr_expense_stripe.utils import (
    STRIPE_FILE_UPLOAD_CONFIG,
    STRIPE_REQUEST_REFUSED_REASONS,
    StripeIssuingDatabaseError,
    format_amount_from_stripe,
    make_request_stripe_proxy,
)

_logger = logging.getLogger(__name__)


class StripeIssuingController(Controller):
    _webhook_url = 'stripe_issuing/webhook'

    @route(f"/{_webhook_url}/<string:company_uuid>", type='http', methods=['POST'], auth='public', csrf=False, save_session=False)
    def stripe_issuing_webhook(self, company_uuid):
        event = request.get_json_data()
        _logger.info(
            'Webhook "%(type)s" event (%(event_id)s) received to "%(url)s" from %(ip)s',
            {
                'type': event['type'],
                'event_id': event['id'],
                'url': f'{self._webhook_url}/{company_uuid}',
                'ip': request.httprequest.remote_addr,
            },
        )
        response_headers = {
            'Stripe-Version': event['api_version'],
            'Content-Type': 'application/json',
        }
        company_sudo = self.env['res.company'].sudo().search([('stripe_issuing_iap_webhook_uuid', '=', company_uuid)])
        if not company_sudo:
            response = {'message': 'Invalid webhook accessed'}
            return request.make_json_response(data=response, headers=response_headers, status=StripeIssuingDatabaseError.DB_WRONG_WEBHOOK)

        env = request.env(
            user=SUPERUSER_ID,
            su=True,
            context={'allowed_company_ids': company_sudo.ids},
        )
        signature_header = request.httprequest.headers.get('Iap-Signature')
        valid = self._validate_signature(company_sudo, signature_header, request.httprequest.data.decode())
        if not valid:
            response = {'message': 'Invalid or outdated signature found in the request'}
            return request.make_json_response(data=response, headers=response_headers, status=StripeIssuingDatabaseError.DB_WRONG_SIGNATURE)

        event_mode = 'live' if event['livemode'] else 'test'
        if company_sudo._get_stripe_mode() != event_mode:
            response = {'message': 'Event ignored as the event mode does not match the company mode'}
            return request.make_json_response(data=response, headers=response_headers)

        status = 200
        try:
            match event['type'].split('.'):
                case ('balance', 'available'):
                    response = self._process_balance_event(env, event)
                case ('issuing_authorization', _multiples):
                    response = self._process_authorization_event(env, event)
                case ('issuing_card', 'updated'):
                    response = self._process_card_event(env, event)
                case ('issuing_dispute', _multiples):
                    response = self._process_dispute_event(env, event)
                case ('issuing_transaction', _multiples):
                    response = self._process_transaction_event(env, event)
                case ('topup', 'succeeded'):
                    response = self._process_topup_event(env, event)
                case _:
                    response = {
                        'approved': False,
                        'message': f"Invalid event type '{event['type']}'",
                    }
        except Exception as e:  # noqa: BLE001 # Catch all exceptions to avoid crashing the webhook and having it disabled by Stripe
            response = {
                'approved': False,
                'message': str(e),
            }
            _logger.error(traceback.format_exc())
            # Because the request awaits a response, we decline the authorization request to prevent the webhook from being disabled by Stripe
            status = StripeIssuingDatabaseError.DB_ERROR if event['type'] != 'issuing_authorization.request' else 200
        return request.make_json_response(data=response, headers=response_headers, status=status)

    @route('/stripe_issuing/upload_file', type='jsonrpc', auth='user', methods=['POST'])
    def stripe_issuing_upload_file(self, model, record_id, field_name, purpose, file_name, b64_file_data, content_type):
        if model != 'hr.expense.stripe.dispute':
            raise UserError(self.env._("You cannot upload stripe attachment for the given model."))

        if not isinstance(record_id, int):
            raise UserError(self.env._("Uploading a file is only supported for single disputes."))

        record = self.env[model].browse(record_id)
        if not record.exists():
            raise UserError(self.env._("The record doesn't exist."))

        record._check_can_upload_stripe_attachment(field_name)

        if not b64_file_data:
            raise UserError(self.env._("No file provided for upload."))

        upload_config = STRIPE_FILE_UPLOAD_CONFIG.get(purpose)
        if not upload_config:
            raise UserError(self.env._("The purpose provided is not valid."))

        if model not in upload_config['supported_models']:
            raise UserError(self.env._("The purpose '%(purpose)s' is not allowed to be used with this model.", purpose=purpose))

        if content_type not in upload_config['mimetypes']:
            raise UserError(self.env._("The content type provided is not valid for the purpose '%(purpose)s'.", purpose=purpose))

        file_data = base64.b64decode(b64_file_data)
        if len(file_data) > upload_config['max_size']:
            MiB = 1024 * 1024
            raise UserError(self.env._(
                "The file provided is too large. Maximum size is %(size)s MiB.",
                size=upload_config['max_size'] // MiB,
            ))

        if not isinstance(file_name, str) or not file_name.strip():
            raise UserError(self.env._("The file name provided is not valid. Only use alpha-numeric characters or '.-_'."))
        file_name = secure_filename(file_name)

        company_sudo = record.company_id.sudo() if 'company_id' in record._fields else self.env.company.sudo()
        route = 'files'
        payload = {
            'account': company_sudo.stripe_id,
            'purpose': purpose,
        }
        files = {'file': (file_name, file_data, content_type)}
        response = make_request_stripe_proxy(company_sudo, route, {}, method='POST', payload=payload, files=files)
        record[field_name] = response['id']

    @route('/stripe_issuing/download_file', type='http', auth='user', methods=['GET'])
    def stripe_issuing_download_file(self, model, record_id, field_name):
        if model != 'hr.expense.stripe.dispute':
            raise UserError(self.env._("You cannot download stripe attachment for the given model."))

        try:
            record_id = int(record_id)  # Given from window.open in params instead of rpc calls, so id is a string here.
        except ValueError:
            raise UserError(self.env._("Downloading a file is only supported for single disputes.")) from None

        record = self.env[model].browse(record_id)
        if not record.exists():
            raise UserError(self.env._("The record doesn't exist."))

        record._check_can_download_stripe_attachment(field_name)

        stripe_file_id = record[field_name]
        if not stripe_file_id:
            raise UserError(self.env._("No file was uploaded for this field."))

        company_sudo = record.company_id.sudo()
        route = 'files/{file_id}'
        route_params = {'file_id': stripe_file_id}
        payload = {'account': company_sudo.stripe_id}
        response = make_request_stripe_proxy(company_sudo, route, route_params, method='GET', payload=payload)

        filename = f'attachment; filename="{response["filename"]}"'

        route = 'files/{file_id}/contents'
        content_type, content = make_request_stripe_proxy(company_sudo, route, route_params, method='GET', payload=payload, raw=True)

        return request.make_response(
            data=content,
            headers=[
                ('Content-Type', content_type),
                ('Content-Disposition', filename),
            ],
        )

    # --------------------------------------------
    # Events processing methods
    # --------------------------------------------

    @api.model
    def _process_authorization_event(self, env, event):
        auth_object = event['data']['object']
        card = env['hr.expense.stripe.card'].search(
            [('stripe_id', '=', auth_object['card']['id']), ('company_id', '=', env.company.id)],
            limit=1,
        )
        if not card:
            raise MissingError(env._("A card that doesn't exist on the database was used"))
        if event['type'] == 'issuing_authorization.request':
            amount = format_amount_from_stripe(auth_object['pending_request']['amount'], card.currency_id)
            mcc_code = auth_object['merchant_data']['category_code']
            country = env['res.country'].search([('code', 'ilike', auth_object['merchant_data']['country'])], limit=1)

            can_pay, refusal_reason = card._can_pay_amount(amount, mcc_code, country)
            if can_pay:
                # We only create it when the capture happens
                return {'message': 'Authorization request approved', 'approved': True}
            else:
                # There will be no capture, we need to create a refused expense to log the refusal reason
                env['hr.expense']._create_from_stripe_authorization(auth_object, refusal_reason)
                return {'message': refusal_reason, 'approved': False}

        if event['type'] in {'issuing_authorization.created', 'issuing_authorization.updated'}:
            default_reason = env._("Unknown reason.")
            default_request_history = [{'approved': False, 'reason': default_reason}]
            request_history = auth_object.setdefault('request_history', default_request_history)[0]
            response_message = ''
            match auth_object['status'], request_history['approved']:
                case 'pending', True:
                    env['hr.expense']._create_from_stripe_authorization(auth_object)
                    response_message = 'Draft expense created'

                case ('closed', False) | ('reversed' | 'expired', False | True):
                    # There will be no capture, we need to create a refused expense to log the refusal reason
                    technical_reason = request_history['reason']
                    if technical_reason == 'webhook_declined':
                        refusal_reason = auth_object['metadata'].get(
                            'message',
                            STRIPE_REQUEST_REFUSED_REASONS.get(technical_reason, default_reason),
                        )
                    elif technical_reason == 'webhook_approved':
                        refusal_reason = env._(
                            "The authorization was approved by the webhook, but was later reversed or closed without any capture."
                        )
                    else:
                        refusal_reason = STRIPE_REQUEST_REFUSED_REASONS.get(technical_reason, default_reason)
                    env['hr.expense']._create_from_stripe_authorization(auth_object, refusal_reason)
                    response_message = 'Refused expense created'

                case _:
                    response_message = 'Event ignored, not a refused or draft expense'
            return {'message': response_message}
        raise ValidationError(env._("Invalid event type '%(invalid_event)s'", invalid_event=event['type']))

    @api.model
    def _process_balance_event(self, env, event):
        bal_object = event['data']['object']
        issuing_object = bal_object['issuing']
        company = env.company
        journal = company.stripe_journal_id
        last_balance_timestamp = journal.stripe_issuing_balance_timestamp
        if last_balance_timestamp >= event['created']:
            return {'message': 'Balance ignored, a more recent one was already received'}
        stripe_currency = journal.stripe_currency_id
        if issuing_object['available']:  # May be empty if 0
            issuing_amount = format_amount_from_stripe(issuing_object['available'][0]['amount'], stripe_currency)
        else:
            issuing_amount = 0

        company.stripe_journal_id.write({
            'stripe_issuing_balance': issuing_amount,
            'stripe_issuing_balance_timestamp': event['created'],
        })

        if stripe_currency.compare_amounts(issuing_amount, 0) < 0:
            amount_to_dispute = -issuing_amount
            # Remove amount from force captures already disputed and not yet reinstated
            disputes = env['hr.expense.stripe.dispute'].search([
                ('state', 'in', ('submitted', 'won')),
                ('reason', '=', 'no_valid_authorization'),
                ('company_id', '=', env.company.id),
            ])
            reinstated_dispute_stripe_ids = {
                stripe_id
                for stripe_id,
                in env['account.bank.statement.line']._read_group(
                    domain=[('stripe_id', 'in', disputes.mapped('stripe_id')), ('amount', '>', 0)],
                    groupby=['stripe_id'],
                )
            }
            disputes = disputes.filtered(lambda d: d.stripe_id not in reinstated_dispute_stripe_ids)
            amount_to_dispute -= sum(disputes.expense_ids.mapped('disputed_amount'))
            env['hr.expense']._dispute_force_captures(amount_to_dispute)

        return {'message': 'Balance updated'}

    @api.model
    def _process_card_event(self, env, event):
        card_object = event['data']['object']
        existing_card = env['hr.expense.stripe.card'].search(
            [('stripe_id', '=', card_object['id']), ('company_id', '=', env.company.id)],
            limit=1,
        )
        if not existing_card:
            raise ValidationError(env._("A card that doesn't exist on the database was used"))

        if (
            card_object['shipping'] and card_object['shipping'].get('status') in {'canceled', 'failure', 'returned'}
            and event['data']["previous_attributes"].get("shipping", {}).get("status")
        ):
            existing_card.with_context(skip_local_update=existing_card.state == 'canceled')._create_or_update_card(state='canceled')
        else:
            existing_card._update_from_stripe(card_object)

        return {'message': 'Card updated'}

    @api.model
    def _process_transaction_event(self, env, event):
        tr_object = event['data']['object']
        authorization_id = tr_object['authorization']
        transaction_id = tr_object['id']

        split_id = False
        if transaction_id and not authorization_id:
            # In case of a force capture
            existing_expenses = env['hr.expense'].search([('stripe_transaction_id', '=', transaction_id)])

        elif authorization_id:
            existing_expenses = env['hr.expense'].search([('stripe_authorization_id', '=', authorization_id)])
            expense_transaction_ids = set(existing_expenses.mapped('stripe_transaction_id')) - {False}
            if expense_transaction_ids and transaction_id not in expense_transaction_ids:
                if len(existing_expenses) == 1:
                    split_id = (existing_expenses.split_expense_origin_id or existing_expenses).id
                else:
                    split_id = next(
                        s_id
                        for s_id
                        in (*existing_expenses.mapped('split_expense_origin_id').ids, min(existing_expenses.ids))
                        if s_id
                    )
                existing_expenses.split_expense_origin_id = split_id
                existing_expenses = env['hr.expense']  # If double transaction is detected, create a new existing_expenses
            elif expense_transaction_ids:
                existing_expenses = existing_expenses.filtered(lambda exp: exp.stripe_transaction_id == transaction_id)

        if tr_object['type'] == 'capture' and not existing_expenses:
            env['hr.expense']._create_from_stripe_transaction(tr_object, split_id=split_id)
        elif tr_object['type'] == 'capture' and existing_expenses:
            existing_expenses._update_from_stripe_transaction(tr_object)
        elif tr_object['type'] == 'refund' and existing_expenses:
            existing_expenses._stripe_cancel_expense_or_reverse_move(tr_object)
        if event['type'] == 'issuing_transaction.created':
            existing_statement_line = env['account.bank.statement.line'].search([('stripe_id', '=', transaction_id)])
            if existing_statement_line:
                # if the event is sent twice
                existing_statement_line._update_from_stripe_transaction(tr_object)
            else:
                env['account.bank.statement.line']._create_from_stripe_transaction(tr_object)
        elif event['type'] == 'issuing_transaction.updated':
            statement_line = env['account.bank.statement.line'].search([('stripe_id', '=', transaction_id)])
            statement_line._update_from_stripe_transaction(tr_object)
        return {'message': 'Expense & Bank Statement Line Created/Updated'}

    @api.model
    def _process_dispute_event(self, env, event):
        dispute_object = event['data']['object']
        existing_expense = env['hr.expense'].search([('stripe_transaction_id', '=', dispute_object['transaction'])], limit=1)

        if not existing_expense:
            raise MissingError(env._("An expense that doesn't exist on the database was used"))

        if (
            dispute_object.get('metadata', {}).get('automated_dispute')
            and event['type'] in {'issuing_dispute.created', 'issuing_dispute.updated', 'issuing_dispute.submitted'}
        ):
            return {'message': "Dispute Event skipped for Automatically Disputed Force Captures with negative balance."}

        if event['type'] in {'issuing_dispute.created', 'issuing_dispute.updated', 'issuing_dispute.submitted', 'issuing_dispute.closed'}:
            env['hr.expense.stripe.dispute'].with_context(from_webhook=True)._create_or_update_from_stripe(dispute_object)

        elif event['type'] == 'issuing_dispute.funds_reinstated':
            # Stripe seems to send this event 2 times in test mode, If this happens in production, consider
            # adding env.cr.commit. A flush wont work, since the 2 events will be using different cursor since
            # they will be on different threads.
            env['account.bank.statement.line']._create_from_stripe_dispute(dispute_object, 'reinstated')

        elif event['type'] == 'issuing_dispute.funds_rescinded':
            env['account.bank.statement.line']._create_from_stripe_dispute(dispute_object, 'rescinded')

        return {'message': "Dispute Created/Updated"}

    @api.model
    def _process_topup_event(self, env, event):
        tu_object = event['data']['object']
        statement_line = env['account.bank.statement.line'].search([('stripe_id', '=', tu_object['id'])])
        if statement_line:
            return {'message': 'Top-up Bank Statement Line already exists, ignoring the event'}
        env['account.bank.statement.line']._create_from_stripe_topup(tu_object)
        return {'message': 'Top-up Bank Statement Line Create/updated'}

    # --------------------------------------------
    # Helpers
    # --------------------------------------------
    @api.model
    def _validate_signature(self, company, signature_header, payload_str):
        if not signature_header or not company:
            return False

        signature_data_dict = {}
        for key_value_str in signature_header.split(','):
            key, value = key_value_str.split('=', 1)
            if key in signature_data_dict:
                # If the key already exists, it means the signature is malformed
                return False
            signature_data_dict[key] = value

        if 'v1' not in signature_data_dict or 't' not in signature_data_dict:
            return False

        signature = base64.b64decode(signature_data_dict['v1'] + '==')  # Ensure padding is correct for base64 decoding
        timestamp = signature_data_dict['t']
        time_since_signed = time.time() - int(timestamp)
        signature_validity = 60 * 5  # 5 min
        if time_since_signed > signature_validity:
            return False
        signed_message = f'{timestamp}.{payload_str}'.encode()
        public_key = company.sudo().stripe_issuing_iap_public_key_id
        return public_key._verify(signed_message, signature)
