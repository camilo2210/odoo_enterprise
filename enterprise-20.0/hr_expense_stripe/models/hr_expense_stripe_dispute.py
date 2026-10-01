from datetime import datetime

from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import LazyTranslate

from odoo.addons.hr_expense_stripe.utils import format_amount_from_stripe, format_amount_to_stripe, make_request_stripe_proxy

_lt = LazyTranslate(__name__)

LOSS_REASONS = {
    'cardholder_authentication_issuer_liability': _lt(
        "This dispute, created for Card-Not-Present fraud, "
        "is invalid because the card network has indicated the cardholder was securely authenticated.\n"
    ),
    'eci5_token_transaction_with_tavv': _lt(
        "This dispute, created under Condition 10.4: Other Fraud, is invalid for an ECI 5 Token Transaction where the "
        "Token Authentication Verification Value (TAVV) was included in the Authorization Request.\n"
    ),
    'excess_disputes_in_timeframe': _lt(
        "This dispute is invalid as more than 35 total disputes have been submitted within 120 calendar days of this dispute.\n"
    ),
    'has_not_met_the_minimum_dispute_amount_requirements': _lt(
        "This dispute has not met the minimum amount threshold set by the card network based on the MCC.\n"
    ),
    'invalid_duplicate_dispute': _lt(
        "This dispute, created under Condition 12.6: Duplicate Processing/Paid by Other Means, has not met the criteria set by Mastercard.\n"
    ),
    'invalid_incorrect_amount_dispute': _lt(
        "This dispute, created under Condition 12.5: Incorrect Amount, has not met the criteria set by Mastercard.\n"
        "The dispute must include evidence of the correct amount.\n"
    ),
    'invalid_no_authorization': _lt(
        "The dispute, created under Condition 11.3: No Authorization, is invalid due to the transaction being authorized "
        "as indicated in the Mastercard Core Rules and Mastercard Product and Service Rules.\n"
    ),
    'invalid_use_of_disputes': _lt(
        "Stripe has determined that this is an invalid use of the card network dispute process; no dispute conditions apply.\n"
    ),
    'merchandise_delivered_or_shipped': _lt(
        "The merchant provided evidence indicating that the merchandise was shipped/delivered.\n"
        "Stripe has evaluated this evidence and determined that it is compelling.\n"
    ),
    'merchandise_or_service_as_described': _lt(
        "The merchant provided information indicating the item/service provided matched the description.\n"
        "Stripe has evaluated this evidence and determined that it is compelling.\n"
    ),
    'not_cancelled': _lt(
        "The cardholder claims they canceled their subscription/order, but the merchant has no record of such cancellation, "
        "nor was one provided by the cardholder.\n"
        "Stripe has evaluated this evidence and determined that it is compelling.\n"
    ),
    'other': _lt("Please contact Odoo for more information about this dispute.\n"),
    'refund_issued': _lt(
        "The dispute is invalid because there is already a refund for the transaction in which the refund and "
        "dispute amounts sum up to more than the original transaction amount.\n"
        "The dispute was automatically rejected due to this discrepancy.\n"
    ),
    'submitted_beyond_allowable_time_limit': _lt(
        "The dispute was submitted past the disputable deadline.\n"
        "The dispute was automatically rejected by the card network.\n"
    ),
    'transaction_3ds_required': _lt(
        "This dispute is invalid because the merchant attempted 3DS for a Card-Not-Present (CNP) transaction, "
        "but the card provider did not have 3DS enabled for the card.\n"
        "The dispute was automatically rejected by the card network.\n"
    ),
    'transaction_approved_after_prior_fraud_dispute': _lt(
        "The cardholder/card provider didn't deactivate the card after claiming fraud on previous transactions.\n"
        "The dispute was automatically rejected by the card network.\n"
    ),
    'transaction_authorized': _lt(
        "The merchant has provided evidence that indicates this transaction was authorized by the cardholder.\n"
        "Stripe has evaluated this evidence and determined that it is compelling.\n"
    ),
    'transaction_electronically_read': _lt(
        "The liability shifts to the issuer for fraudulent disputes if the card-present transaction was authorized with a chip-reading terminal.\n"
        "This dispute was automatically rejected by the card network.\n"
    ),
    'transaction_qualifies_for_mastercard_easy_payment_service': _lt(
        "This dispute is invalid since the transaction qualifies for Mastercard Easy Payment Service (MEPS) Transaction, "
        "which allows businesses to accept Mastercard without customers pausing to sign or enter a PIN.\n"
        "With MEPS, the liability shifts onto the card provider.\n"
        "The dispute was automatically rejected by Mastercard.\n"
    ),
    'transaction_unattended': _lt(
        "This dispute is invalid as the transaction was unattended, chip-initiated, and online authorized "
        "(e.g., swiping a chip card at an unattended gas pump, parking meter, or ATM).\n"
        "The liability is on the card provider for these types of transactions.\n"
        "The dispute was automatically rejected by the card network.\n"
    ),
}


class HrExpenseStripeDispute(models.Model):
    _name = 'hr.expense.stripe.dispute'
    _description = "HR Expense Stripe Dispute"

    stripe_id = fields.Char(string="Stripe Dispute ID", readonly=True, copy=False, index=True)
    stripe_transaction_id = fields.Char(string="Stripe Transaction ID", required=True, readonly=True, index=True)
    card_id = fields.Many2one(comodel_name='hr.expense.stripe.card', required=True, readonly=True, index=True)
    currency_id = fields.Many2one(comodel_name='res.currency', required=True, readonly=True)
    amount = fields.Monetary(
        string="Disputed Amount",
        currency_field='currency_id',
        compute='_compute_amount',
        inverse='_inverse_amount',
        store=True,
    )
    reason = fields.Selection(
        required=True,
        selection=[
            ('fraudulent', "Fraudulent"),
            ('not_received', "Not Received"),
            ('duplicate', "Duplicate Charge"),
            ('not_as_described', "Not as Described"),
            ('no_valid_authorization', "No Valid Authorization"),
            ('canceled', "Previously Canceled"),
            ('other', "Other"),
        ],
    )
    state = fields.Selection(
        default='unsubmitted',
        selection=[
            ('unsubmitted', "Draft"),
            ('submitted', "Submitted"),
            ('won', "Won"),
            ('lost', "Lost"),
            ('expired', "Expired"),
        ],
    )
    submitted_by = fields.Many2one(comodel_name='res.users', readonly=True, copy=False)
    loss_reason = fields.Char(readonly=True)

    expense_ids = fields.One2many(comodel_name='hr.expense', inverse_name='dispute_id')
    company_id = fields.Many2one(comodel_name='res.company', required=True, readonly=True)
    has_only_one_expense = fields.Boolean(compute='_compute_has_only_one_expense')
    can_submit = fields.Boolean(compute='_compute_can_submit')

    additional_documentation = fields.Char(
        help="Supporting files or images. Please combine them into a PDF or JPEG, and upload it here.",
    )
    explanation = fields.Text(help="Include timelines, cardholder rationale, and additional evidence.")
    product_type = fields.Selection(selection=[('merchandise', "Merchandise"), ('service', "Service or digital goods")])
    product_description = fields.Text()
    expected_at = fields.Date(string="Expected Date", help="Date the cardholder expected to receive the purchase.")
    return_status = fields.Selection(selection=[('successful', "Accepted"), ('merchant_rejected', "Rejected")])
    canceled_at = fields.Date(
        string="Cancellation Date",
        help="Date the cardholder canceled the purchase. Cancellation is required to file a Dispute.",
    )
    cancellation_reason = fields.Text(help="Cardholder's rationale for canceling the purchase.")
    returned_at = fields.Date(string="Return Date", help="Date the cardholder initiated return of the purchase.")
    proof_of_original_payment = fields.Selection(
        selection=[
            ('card_statement', "Card Statement"),
            ('cash_receipt', "Cash Receipt"),
            ('check_image', "Check Image"),
            ('original_transaction', "Original Transaction ID"),
        ],
    )
    card_statement = fields.Char(help="Copy of the card statement showing that the product had already been paid for.")
    cash_receipt = fields.Char(help="Copy of the receipt showing that the product had been paid for in cash.")
    check_image = fields.Char(help="Image of the front and back of the check that was used to pay for the product.")
    original_transaction = fields.Char(
        string="Original Transaction ID",
        help="Transaction (e.g., ipi_…) that the disputed transaction is a duplicate of. "
             "Of the two or more transactions that are copies of each other, this is original undisputed one.",
    )
    received_at = fields.Date(string="Received Date", help="Date the cardholder received the purchase.")
    return_description = fields.Text(help="Details on how the merchandise was returned.")
    policy_compliance = fields.Selection(selection=[('compliant', "Compliant with policy"), ('no_policy', "No policy")])

    @api.constrains('amount')
    def _check_disputed_amount(self):
        for dispute in self:
            if (len(dispute.expense_ids) != 1):
                expenses_amount = sum(dispute.expense_ids.mapped('disputed_amount'))
                if dispute.currency_id.compare_amounts(dispute.amount, expenses_amount) != 0:
                    raise ValidationError(self.env._("The amount disputed should match the amount on the expenses."))

    @api.depends('expense_ids')
    def _compute_has_only_one_expense(self):
        for dispute in self:
            dispute.has_only_one_expense = len(dispute.expense_ids) == 1

    @api.depends('expense_ids.state')
    def _compute_can_submit(self):
        for dispute in self:
            dispute.can_submit = all(expense.state == 'paid' for expense in dispute.expense_ids)

    @api.depends('expense_ids.disputed_amount')
    def _compute_amount(self):
        for dispute in self:
            new_amount = sum(dispute.expense_ids.mapped('disputed_amount'))  # To prevent concurrency updates
            currency = dispute.currency_id or dispute.company_id.stripe_currency_id
            if (
                dispute.state == 'unsubmitted'
                and currency
                and currency.compare_amounts(dispute.amount, new_amount) != 0
            ):
                dispute.amount = new_amount

    def _inverse_amount(self):
        for dispute in self:
            if len(dispute.expense_ids) == 1:
                dispute.expense_ids.disputed_amount = dispute.amount

    @api.model_create_multi
    def create(self, vals_list):
        disputes = super().create(vals_list)

        for expense in disputes.expense_ids:
            dispute = expense.dispute_id
            expense.message_post(body=dispute._get_html_link(self.env._("A dispute has been created.")))
        return disputes

    def write(self, vals):
        # Prevent modification of dispute details once submitted
        if (
            set(self.mapped('state')) - {'unsubmitted'}
            and set(vals) - {'loss_reason', 'state'}
            and not self.env.context.get('from_webhook')
        ):
            raise UserError(self.env._("Cannot modify the dispute details once it has been submitted."))

        disputes_not_yet_ended = self.filtered(lambda dispute: dispute.state not in {'won', 'lost'})
        res = super().write(vals)

        if set(vals) - {'stripe_id', 'state', 'loss_reason'}:
            for expense in self.filtered(lambda d: d.state == 'unsubmitted').expense_ids:
                expense.message_post(body=self.env._("The dispute has been updated."))
        if vals.get('state') in {'won', 'lost'}:
            for dispute in disputes_not_yet_ended:
                dispute._send_status_emails(dispute.state)
        return res

    def action_submit(self):
        if not self.env.user.has_group('hr_expense.group_hr_expense_manager') and not self.env.su:
            raise UserError(self.env._("Only an expense manager can submit a dispute."))

        if set(self.mapped('expense_ids.state')) - {'paid'}:
            raise UserError(self.env._("The dispute can only be submitted if the journal entries of all related expenses are posted."))

        for dispute in self.filtered(lambda disp: not disp.stripe_id):
            dispute.action_create_or_update_dispute()

        for dispute in self:
            route = 'disputes/{dispute_id}/submit'
            route_params = {'dispute_id': dispute.stripe_id}
            payload = {'account': dispute.company_id.sudo().stripe_id}
            response = make_request_stripe_proxy(dispute.company_id.sudo(), route, route_params, method='POST', payload=payload)
            dispute._create_or_update_from_stripe(response)
            dispute._send_status_emails('submitted')

    def _send_status_emails(self, email_type):
        self.ensure_one()
        if email_type not in {'submitted', 'won', 'lost'}:
            raise UserError(self.env._("Invalid email type must be one of 'submitted', 'won' or 'lost'."))
        template_ref = f'hr_expense_stripe.email_template_hr_expense_stripe_dispute_{email_type}'

        receiver = self.env.ref('base.user_admin') if self.submitted_by == self.env.ref('base.user_root') else self.submitted_by
        email_to = receiver.work_email or receiver.email
        template_context = {
            'submitted_by': receiver.name,
            'loss_reason': LOSS_REASONS.get(self.loss_reason, self.env._("No reason provided")) if email_type == 'lost' else False,
            'lang': receiver.lang,
        }
        template = self.env.ref(template_ref, raise_if_not_found=False)
        if template and email_to:
            template.with_context(**template_context).send_mail_batch(
                self.expense_ids.ids,
                email_values={'email_to': email_to, 'email_from': self.env.ref('base.partner_root').email},
            )
        else:
            for expense in self.expense_ids:
                expense.message_post(body=self.env._('The dispute has been %(status)s.', status=email_type))

    def action_create_or_update_dispute(self):
        if not self.env.user.has_group('hr_expense.group_hr_expense_manager') and not self.env.su:
            raise UserError(self.env._("Only an expense manager can create or update a dispute."))

        if any(not dispute.reason for dispute in self):
            raise UserError(self.env._("A reason must be set to create or update a dispute."))

        for dispute in self:
            reason = f'{dispute.product_type}_not_as_described' if dispute.reason == 'not_as_described' else dispute.reason
            payload = {
                'account': dispute.company_id.sudo().stripe_id,
                'amount': format_amount_to_stripe(dispute.amount, dispute.currency_id),
                'evidence[reason]': reason,
            }

            if self.env.context.get('automated_dispute'):
                payload['metadata[automated_dispute]'] = True

            if not dispute.stripe_id:
                payload['transaction'] = dispute.stripe_transaction_id
                route = 'disputes'
                route_params = {}
            else:
                route = 'disputes/{dispute_id}'
                route_params = {'dispute_id': dispute.stripe_id}

            date_fields = {'expected_at', 'canceled_at', 'returned_at', 'received_at'}
            optional_fields = {'additional_documentation', 'card_statement', 'cash_receipt', 'check_image', 'explanation'}
            fields_for_reason = {
                'canceled': {'canceled_at', 'cancellation_reason', 'expected_at', 'product_description', 'product_type', 'return_status', 'returned_at'},
                'merchandise_not_as_described': {'received_at', 'return_description', 'return_status', 'returned_at'},
                'service_not_as_described': {'canceled_at', 'cancellation_reason', 'received_at'},
                'not_received': {'expected_at', 'product_description', 'product_type'},
                'other': {'product_description', 'product_type'},
            }

            for field in fields_for_reason.get(reason, set()) | {'additional_documentation', 'explanation'}:
                value = dispute[field]
                if field in date_fields:
                    value = (value and int(fields.Datetime.to_datetime(f'{value} 00:00:00').timestamp())) or False
                elif field in optional_fields and not value:
                    value = ''
                payload[f'evidence[{reason}][{field}]'] = value

            if reason == 'canceled':
                payload['evidence[canceled][cancellation_policy_provided]'] = dispute.policy_compliance == 'compliant'
            elif reason == 'duplicate':
                # Since Stripe requires that only one is provided, we set empty values for the others
                if not dispute.proof_of_original_payment:
                    raise UserError(self.env._("A proof of original payment must be provided for a duplicate payment dispute."))
                for field in ('card_statement', 'cash_receipt', 'check_image', 'original_transaction'):
                    payload[f'evidence[duplicate][{field}]'] = ''

                payload[f'evidence[duplicate][{dispute.proof_of_original_payment}]'] = dispute[dispute.proof_of_original_payment]

            payload = {k: v for k, v in payload.items() if v is not False}
            response = make_request_stripe_proxy(dispute.company_id.sudo(), route, route_params, method='POST', payload=payload)

            dispute.with_context(from_webhook=False)._create_or_update_from_stripe(response)

    def _create_or_update_from_stripe(self, dispute_object):
        """
        Creates or update a dispute from a Stripe dispute object See: https://docs.stripe.com/api/issuing/disputes/object
        """
        if len(self) > 1:
            self.ensure_one()

        expenses = self.env['hr.expense'].search([('stripe_transaction_id', '=', dispute_object['transaction'])])
        if not expenses:
            raise UserError(self.env._("Failed to find the related expense for the dispute from Stripe."))

        existing_dispute = self
        if not existing_dispute:  # Only one dispute can be linked to a transaction, so only ever one dispute will be set here
            existing_dispute = expenses.dispute_id

        stripe_journal = (existing_dispute.company_id or self.env.company).stripe_journal_id
        new_vals = {}
        if not existing_dispute.stripe_id:
            new_vals['stripe_id'] = dispute_object['id']
        if not existing_dispute.stripe_transaction_id:
            new_vals['stripe_transaction_id'] = dispute_object['transaction']
        if not existing_dispute.company_id:
            new_vals['company_id'] = self.env.company.id
        if not existing_dispute.card_id:
            card_ids = expenses.card_id.ids
            if len(card_ids) != 1:
                raise UserError(self.env._("Multiple cards for one dispute is not possible."))
            new_vals['card_id'] = card_ids[0]

        dispute_currency = (
            existing_dispute.currency_id
            or self.env['res.currency'].with_context(active_test=False).search(
                [('name', '=ilike', dispute_object['currency'])],
                limit=1,
            )
            or stripe_journal.stripe_currency_id
        )
        if not existing_dispute.currency_id:
            new_vals['currency_id'] = dispute_currency.id
        if not existing_dispute.expense_ids:
            new_vals['expense_ids'] = [Command.link(expense.id) for expense in expenses]
        if not existing_dispute or existing_dispute.state != dispute_object['status']:
            states = {self.env['hr.expense.stripe.dispute']: 0, 'unsubmitted': 1, 'submitted': 2, 'won': 3, 'lost': 3, 'expired': 3}
            if states[existing_dispute and existing_dispute.state] < states[dispute_object['status']]:
                new_vals['state'] = dispute_object['status']
                if new_vals['state'] == 'submitted':
                    new_vals['submitted_by'] = self.env.user.id
        amount = format_amount_from_stripe(dispute_object['amount'], dispute_currency)
        if dispute_currency.compare_amounts(existing_dispute.amount, amount) != 0:
            new_vals['amount'] = amount

        reason = dispute_object['evidence']['reason']
        reason = 'not_as_described' if reason in {'merchandise_not_as_described', 'service_not_as_described'} else reason
        if not existing_dispute or existing_dispute.reason != reason:
            new_vals['reason'] = reason
        if dispute_object.get('loss_reason') and (not existing_dispute or not existing_dispute.loss_reason):
            new_vals['loss_reason'] = dispute_object['loss_reason']

        stripe_fields = {
            'additional_documentation', 'explanation', 'product_type', 'product_description', 'return_status',
            'cancellation_reason', 'card_statement', 'cash_receipt', 'check_image', 'original_transaction', 'return_description',
        }
        stripe_timestamp_fields = {'expected_at', 'canceled_at', 'returned_at', 'received_at'}

        evidence_data = dispute_object['evidence'][dispute_object['evidence']['reason']]
        for field in stripe_fields | stripe_timestamp_fields:
            if field not in evidence_data:
                continue

            value = evidence_data[field] or False
            if field in stripe_timestamp_fields and value:
                value = datetime.fromtimestamp(value).date()

            if value != existing_dispute[field]:
                new_vals[field] = value

        if 'cancellation_policy_provided' in evidence_data:
            policy_compliance = 'compliant' if evidence_data['cancellation_policy_provided'] else 'no_policy'
            if policy_compliance != existing_dispute.policy_compliance:
                new_vals['policy_compliance'] = policy_compliance
        proof_of_original_payment = next((field for field in ('card_statement', 'cash_receipt', 'check_image', 'original_transaction') if new_vals.get(field)), False)
        if proof_of_original_payment and (not existing_dispute or existing_dispute.proof_of_original_payment != proof_of_original_payment):
            new_vals['proof_of_original_payment'] = proof_of_original_payment

        if not new_vals:
            return  # This would trigger concurrent access as write always tries to write write_uid and write_date even if new_vals is empty

        if existing_dispute:
            existing_dispute.write(new_vals)
        else:
            self.create(new_vals)

    def _check_can_upload_stripe_attachment(self, field_name):
        self.ensure_one()

        if not (
            self.env.user.has_group('hr_expense.group_hr_expense_manager')
            or self.env.su
        ):
            raise AccessError(self.env._("Only an expense manager can edit a dispute."))

        if self.state != 'unsubmitted':
            raise UserError(self.env._("A dispute must be unsubmitted to be able to be updated."))

        if field_name not in {'additional_documentation', 'card_statement', 'cash_receipt', 'check_image'}:
            raise UserError(self.env._("The specified field doesn't support attachments."))

    def _check_can_download_stripe_attachment(self, field_name):
        self.ensure_one()

        if not (
            self.env.user.has_group('hr_expense.group_hr_expense_manager')
            or self.env.user in self.expense_ids.employee_id.user_id
            or self.env.su
        ):
            raise AccessError(self.env._("You cannot download an attachment of a dispute you're not linked to."))

        if field_name not in {'additional_documentation', 'card_statement', 'cash_receipt', 'check_image'}:
            raise UserError(self.env._("The specified field doesn't support attachments."))
