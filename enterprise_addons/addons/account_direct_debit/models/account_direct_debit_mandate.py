import re
from datetime import date, datetime

from odoo import api, fields, models
from odoo.exceptions import AccessError, RedirectWarning, UserError, ValidationError
from odoo.models import to_record_ids
from odoo.tools import date_utils, format_date


class AccountDirectDebitMandate(models.Model):
    """ A mandate sent to give consent to a company to collect the payments associated
    to their invoices using a direct debit scheme
    (e.g. SEPA Direct Debit or CPA 005 Pre-Authorized Debit).
    """
    _name = 'account.direct.debit.mandate'
    _inherit = ['mail.thread.main.attachment', 'mail.activity.mixin']
    _description = "Direct Debit Mandate"
    _check_company_auto = True
    _order = 'start_date, id'

    _name_unique = models.Constraint(
        'unique(name)',
        "Mandate identifier must be unique! Please choose another one.",
    )

    mandate_type = fields.Selection(
        selection=[],  # Extended in concrete mandates schemes
        string="Mandate Type",
        compute='_compute_mandate_type',
        store=True,
        readonly=False,
        required=True,
        precompute=True,
    )
    display_mandate_type = fields.Boolean(compute='_compute_display_mandate_type')
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('cancelled', 'Cancelled'),
            ('revoked', 'Revoked'),
            ('closed', 'Closed'),
        ],
        readonly=True,
        default='draft',
        required=True,
        tracking=True,
        help="Draft: Validate before use.\n"
             "Active: Valid mandates to collect payments.\n"
             "Cancelled: Mandates never validated.\n"
             "Closed: Expired or manually closed mandates. Previous transactions remain valid.\n"
             "Revoked: Fraudulent mandates. Previous invoices might need reimbursement.\n"
    )
    is_sent = fields.Boolean(string="Sent to the customer", default=False, tracking=True)

    # one-off mandates are fully supported, but hidden to the user for now. Let's see if they need it.
    one_off = fields.Boolean(
        string="One-off Mandate",
        default=False,
        help="True if and only if this mandate can be used for only one transaction. It will automatically go from 'active' to 'closed' after its first use in payment if this option is set.\n",
    )

    name = fields.Char(
        string="Identifier",
        required=True,
        help="The unique identifier of this mandate.",
        default=lambda self: datetime.now().strftime('%f%S%M%H%d%m%Y'),
        copy=False,
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Customer",
        required=True,
        index=True,
        check_company=True,
        help="Customer whose payments are to be managed by this mandate.",
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
        help="Company for whose invoices the mandate can be used.",
    )
    country_code = fields.Char(related='company_id.account_fiscal_country_id.code')
    partner_bank_id = fields.Many2one(
        comodel_name='res.partner.bank',
        string="Bank Account",
        domain="[('partner_id', '=', partner_id)]",
        check_company=True,
        help="Account of the customer to collect payments from.",
    )
    start_date = fields.Date(
        string="Start Date",
        required=True,
        default=fields.Date.context_today,
        help="Date from which the mandate can be used (inclusive).",
    )
    end_date = fields.Date(
        string="End Date",
        help="Date until which the mandate can be used. It will automatically be closed after this date.",
    )
    expiration_warning_already_sent = fields.Boolean(
        string="Expiration warning sent",
        default=False,
        readonly=True,
        copy=False,
    )
    last_validity_check_time = fields.Datetime(readonly=True, copy=False)
    pre_notification_period = fields.Integer(
        string="Pre-notification",
        compute='_compute_pre_notification_period',
        store=True,
        readonly=False,
        precompute=True,
        help="The minimum notice period in days, used to inform the customer prior to collection.",
    )
    alerts = fields.Json(compute='_compute_alerts')
    paid_invoice_ids = fields.One2many(
        comodel_name='account.move',
        compute='_compute_from_moves',
        string="Invoices Paid",
        help="Invoices paid using this mandate.",
    )
    paid_invoices_nber = fields.Integer(
        string="Paid Invoices Number",
        compute='_compute_from_moves',
        help="Number of invoices paid with this mandate.",
    )
    payment_ids = fields.One2many(
        comodel_name='account.payment',
        string="Payments",
        compute='_compute_from_moves',
        help="In-process and completed payments generated under this mandate.",
    )
    payments_to_collect_nber = fields.Integer(
        string="Direct Debit Payments to Collect",
        compute='_compute_from_moves',
        help="Number of in-process and completed payments generated under this mandate.",
    )
    mandate_pdf_file = fields.Binary(
        string="Mandate Form PDF",
        attachment=True,
        copy=False,
        readonly=True,
    )

    # ---------- CONSTRAINS ----------

    @api.constrains('end_date', 'start_date')
    def _validate_end_date(self):
        for record in self:
            if record.end_date and record.end_date < record.start_date:
                raise UserError(self.env._("The end date of the mandate must be posterior or equal to its start date."))

    @api.constrains('pre_notification_period')
    def _validate_pre_notification_period(self):
        for mandate in self:
            minimum = mandate._get_min_pre_notification_period()
            if mandate.pre_notification_period < minimum:  # Minimum required for collection
                raise UserError(self.env._(
                    "The pre-notification period must be at least %s days to allow enough time for the "
                    "customer to check that their account is adequately funded.",
                    minimum,
                ))

    @api.constrains('partner_id', 'partner_bank_id')
    def _validate_partner_bank_id(self):
        for mandate in self:
            if mandate.partner_bank_id and mandate.partner_id != mandate.partner_bank_id.partner_id:
                raise ValidationError(self.env._("Mandate customer and bank account need to match."))

    # ---------- COMPUTES ----------

    @api.depends('country_code')
    def _compute_mandate_type(self):
        # TO OVERRIDE
        selection = self._fields['mandate_type']._description_selection(self.env)
        self.mandate_type = selection[0][0] if len(selection) else None

    @api.depends('partner_id', 'end_date')
    def _compute_display_name(self):
        for mandate in self:
            name = mandate.partner_id.name or self.env._("Draft Mandate")
            if mandate.end_date:
                name += f' - {format_date(mandate.env, mandate.end_date)}'
            mandate.display_name = name

    @api.depends('partner_id')
    def _compute_alerts(self):
        for mandate in self:
            alerts = {}
            commercial_partner = mandate.partner_id.commercial_partner_id
            if mandate.partner_id != commercial_partner:
                alerts['not_commercial_partner'] = {
                    'level': 'warning',
                    'message': self.env._(
                        "The selected customer is a child of %s. "
                        "Make sure the mandate isn't meant for the parent contact.",
                        commercial_partner.name,
                    ),
                    'action_text': self.env._("Check Contact"),
                    'action': commercial_partner._get_records_action(name=self.env._("Parent Contact")),
                }
            mandate.alerts = alerts

    @api.depends('company_id')
    def _compute_display_mandate_type(self):
        selection = self._fields['mandate_type']._description_selection(self.env)
        self.display_mandate_type = len(selection) > 1

    @api.depends('mandate_type')
    def _compute_pre_notification_period(self):
        for mandate in self:
            mandate.pre_notification_period = mandate._get_min_pre_notification_period()

    @api.depends('company_id')
    def _compute_from_moves(self):
        ''' Retrieve the invoices reconciled to the payments through the reconciliation (account.partial.reconcile). '''
        stored_mandates = self.filtered('id')
        if not stored_mandates:
            self.paid_invoices_nber = 0
            self.payments_to_collect_nber = 0
            self.paid_invoice_ids = False
            self.payment_ids = False
            return

        results = dict(
            self.env['account.payment']._read_group([
                ('mandate_id', 'in', self.ids),
                ('payment_method_code', 'in', list(self.env['account.payment.method']._get_mandate_type_per_code())),
                ('state', 'in', ('reconciled', 'paid')),
            ], groupby=['mandate_id'], aggregates=['id:recordset'])
        )

        for mandate in self:
            payments = results.get(mandate, self.env['account.payment'])
            mandate.payment_ids = payments
            mandate.payments_to_collect_nber = len(payments)
            invoices = payments.reconciled_invoice_ids.filtered(lambda move: move.payment_state == 'paid')
            mandate.paid_invoice_ids = invoices
            mandate.paid_invoices_nber = len(invoices)

    # ---------- HOOKS - to be extended/overriden by concrete mandates ----------

    def _get_min_pre_notification_period(self):
        """ Minimum pre-notification period (in days) imposed by the scheme. """
        return 2

    def _get_inactivity_expiry_delay(self):
        """ Delay after which the scheme considers a mandate expired, counted from
        the last collection or, if there was none, from the start date.
        `None` when the scheme has no such rule.
        """
        return None

    def _get_send_mail_template(self):
        """ TO BE OVERRIDDEN The mail.template used by the Send & Print wizard. """
        raise NotImplementedError()

    def _get_expiry_mail_template(self):
        """ The mail.template used to warn about an upcoming expiry. If not set, no expiry email will be send. """
        return None

    def _get_report_base_filename(self):
        """ The base filename for the report. """
        return re.sub(r'\W+', '_', self.env._("mandate_%s", self.name))

    def _get_report_template(self):
        """ The XML ID of the QWeb template for this mandate scheme type. """
        raise NotImplementedError()

    # ---------- BUSINESS METHODS ----------

    def _check_bank_account_for_validation(self):
        """ Validation of the bank account before activating the mandate. """
        self.ensure_one()
        if not self.partner_bank_id:
            raise UserError(self.env._("A customer bank account is required to validate a direct debit mandate."))

        if not self.partner_bank_id.allow_out_payment:
            can_trust = self.partner_bank_id._user_can_trust()
            message = self.env._(
                "The bank account %(account_number)s of %(partner_name)s must be trusted before it can be used "
                "in a direct debit mandate.",
                account_number=self.partner_bank_id.account_number,
                partner_name=self.partner_bank_id.partner_id.display_name,
            )
            if not can_trust:
                message += self.env._("\nAsk your administrator to trust it.")
            raise RedirectWarning(
                message,
                action=self.partner_bank_id._get_records_action(
                    name=self.env._("Bank Account"),
                    # The trust toggle only lives on this (primary) view.
                    views=[(self.env.ref('account.view_partner_bank_form_inherit_account').id, 'form')],
                ),
                button_text=self.env._("Check bank account") if can_trust else self.env._("View bank account"),
            )

    @api.model
    def _get_usable_mandate_domain(self, companies, partners, date, mandate_type=None):
        """ Domain matching the mandates usable at `date` for the given partners. """
        domain = [
            ('state', '=', 'active'),
            ('start_date', '<=', date),
            '|', ('end_date', '=', False), ('end_date', '>=', date),
            ('partner_id', 'in', to_record_ids(partners)),
            *self._check_company_domain(companies),
        ]
        if mandate_type:
            domain.append(('mandate_type', '=', mandate_type))
        return domain

    @api.model
    def _get_usable_mandate(self, company, partner, date, mandate_type=None):
        """ Returns the first mandate found that can be used, accordingly to given parameters
        or none if there is no such mandate.
        """
        return self.search(self._get_usable_mandate_domain(company, partner, date, mandate_type=mandate_type), limit=1)

    @api.model
    def _get_mandate_availability_alerts(self, mandate_type, partners_without_mandate):
        if not partners_without_mandate:
            mandate_label = dict(self._fields['mandate_type']._description_selection(self.env)).get(mandate_type, "")
            return {'mandate_available': {
                'message': self.env._("Good news! A valid %s Mandate is available.", mandate_label),
                'level': 'success',
            }}

        alert = {
            'message': self.env._(
                "Oops! No valid mandate for the following partner(s): %s",
                ", ".join(partners_without_mandate.mapped('name')),
            ),
            'level': 'warning',
        }
        if len(partners_without_mandate) == 1 and self.has_access('read'):
            # a single customer can be sent straight to their mandates
            alert['action_text'] = self.env._("Create it.")
            alert['action'] = partners_without_mandate.action_open_mandates()
        else:
            alert['action_text'] = self.env._("Check partner(s)")
            alert['action'] = partners_without_mandate._get_records_action(name=self.env._("Partner(s)"))
        return {'no_mandate': alert}

    def _update_and_partition_state_by_validity(self):
        """ Helper method to check whether a mandate can still be used or not (and if we're nearing its expiration date, to warn users)
        This also close mandates that are past their validity date
        :return: the mandates grouped under 'valid', 'expiring' or 'invalid'. Empty groups are absent from the dict.
        :rtype: dict
        """
        today = fields.Date.context_today(self)
        expiry_date_per_mandate = self._get_expiry_date_per_mandate()
        warning_delay = date_utils.relativedelta(days=30)

        # Closing invalid mandates that haven't been closed yet, so that they fall into 'invalid' below
        self.filtered(
            lambda mandate: mandate.state == 'active'
            and mandate.start_date <= today
            and expiry_date_per_mandate[mandate] < today
        ).state = 'closed'

        def classify(mandate):
            if mandate.state != 'active' or today < mandate.start_date:
                return 'invalid'
            return 'expiring' if today + warning_delay >= expiry_date_per_mandate[mandate] else 'valid'

        return self.grouped(classify)

    def _get_expiry_date_per_mandate(self):
        """ The mandate expires on its end date, or once dormant for the delay imposed by
        its scheme, whichever comes first. `date.max` when neither applies.
        """
        expiry_date_per_mandate = {}
        latest_payment_date_per_mandate = dict(self.env['account.payment']._read_group([
                ('mandate_id', 'in', self.ids),
                ('payment_method_code', 'in', list(self.env['account.payment.method']._get_mandate_type_per_code())),
                ('state', '=', 'reconciled'),
            ],
            groupby=['mandate_id'],
            aggregates=['date:max'],
        ))
        for mandate in self:
            dates = [mandate.end_date or date.max]
            if inactivity_delay := mandate._get_inactivity_expiry_delay():
                last_payment_date = latest_payment_date_per_mandate.get(mandate) or mandate.start_date
                dates.append(last_payment_date + inactivity_delay)
            expiry_date_per_mandate[mandate] = min(dates)

        return expiry_date_per_mandate

    def _send_expiry_reminder(self):
        """ Send an expiry-warning reminder to each mandate in self, batched by mail template
        since it can differ per mandate scheme.
        """
        for template, mandates in self.grouped(lambda mandate: mandate._get_expiry_mail_template()).items():
            if not template:
                continue
            mandates.message_post_with_source(
                source_ref=template,
                subtype_id=self.env['ir.model.data']._xmlid_to_res_id('mail.mt_note'),
            )
            mandates.expiration_warning_already_sent = True

    def _ensure_required_data(self):
        """ Helper to make sure we don't send/validate a mandate missing the required data """
        if stateless_partners := self.partner_id.filtered(lambda partner: not partner.country_id):
            raise RedirectWarning(
                self.env._("The customer must have a country"),
                action=stateless_partners._get_records_action(name=self.env._("Stateless customer")),
                button_text=(
                    self.env._("Open customer") if len(stateless_partners) == 1 else self.env._("Open customers")
                ),
            )

    # ---------- CRUD ----------

    @api.ondelete(at_uninstall=False)
    def _unlink_if_draft(self):
        if self.filtered(lambda m: m.state != 'draft'):
            raise UserError(self.env._("Only draft mandates can be deleted."))

    # ---------- ACTIONS ----------

    def action_send_and_print(self):
        self.ensure_one()
        self._ensure_required_data()
        template = self._get_send_mail_template()

        return {
            'name': self.env._("Send"),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'account.mandate.send.wizard',
            'target': 'new',
            'context': {
                'default_mandate_id': self.id,
                'default_template_id': template.id,
            },
        }

    def action_validate_mandate(self):
        """ Called by the 'validate' button of the form view. """
        if not self.env.user.has_group('account.group_validate_bank_account'):
            raise AccessError(self.env._("You don't have the rights to validate direct debit mandates."))
        self._ensure_required_data()

        for mandate in self:
            mandate._check_bank_account_for_validation()
            if mandate.state == 'draft':
                mandate.state = 'active'

    def action_revoke_mandate(self):
        """ Called by the 'revoke' button of the form view. """
        self.state = 'revoked'

    def action_cancel_mandate(self):
        self.state = 'cancelled'

    def action_close_mandate(self):
        """ Called by the 'close' button of the form view.
        Also automatically triggered by one-off mandate when they are used.
        """
        today = fields.Date.context_today(self)
        for record in self:
            if record.state not in ('revoked', 'closed'):
                record.end_date = today
                record.state = 'closed'

    def action_view_paid_invoices(self):
        return self.paid_invoice_ids._get_records_action(name=self.env._("Paid Invoices"))

    def action_view_payments_to_collect(self):
        return self.payment_ids._get_records_action(name=self.env._("Payments to Collect"))

    # ---------- CRONS ----------

    @api.model
    def cron_update_and_remind_expired_mandates(self, batch_size=1000):
        today = fields.Datetime.today()
        domain = [
            ('state', '=', 'active'),
            '|', ('last_validity_check_time', '=', False), ('last_validity_check_time', '<', today),
        ]
        mandates = self.search(domain, order='last_validity_check_time asc nulls first', limit=batch_size)
        if not mandates:
            return

        mandates_per_validity = mandates._update_and_partition_state_by_validity()
        if valid_mandates := mandates_per_validity.get('valid'):
            # Reset the field if a new payment came, resetting the period
            valid_mandates.filtered('expiration_warning_already_sent').expiration_warning_already_sent = False
        if expiring_mandates := mandates_per_validity.get('expiring'):
            expiring_mandates.filtered(lambda m: not m.expiration_warning_already_sent)._send_expiry_reminder()

        mandates.last_validity_check_time = fields.Datetime.now()

        remaining = self.search_count(domain) if len(mandates) == batch_size else 0
        self.env['ir.cron']._commit_progress(len(mandates), remaining=remaining)
