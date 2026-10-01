import logging

from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tools import SQL
from odoo.tools.misc import format_date, get_lang

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    automatic_invoice_reminder = fields.Boolean(string="Automatic Invoice Reminders", compute='_compute_automatic_invoice_reminder')
    followup_next_action_date = fields.Date(
        string='Next Reminder',
        copy=False,
        company_dependent=True,
        help="No Reminder action will be taken before this date.",
    )
    last_reminder = fields.Date(
        string="Last Reminder Date",
        compute='_compute_last_reminder_date',
        help="Date when reminder was last sent via email.",
    )
    followup_reminder_type = fields.Selection(
        selection=[('automatic', 'Automatic'), ('manual', 'Manual')],
        string="Reminders",
        default='automatic',
        help="""Choose how Reminders reminders are processed for this partner.
                'Manual' pauses all automatic reminders and level updates for this partner.""")
    # readonly=False in order to be able to edit it directly in the view form, without having to click on 'Edit'
    # It's mainly used for usability purposes to easily include/exclude unreconciled move lines
    unreconciled_aml_ids = fields.One2many('account.move.line', compute='_compute_total_due', readonly=False)
    # These two fields are meant to receive the due and overdue amounts, including asset_receivable AND liability_payable accounts
    # In opposition to the total_due and total_overdue fields which only take into account asset_receivable accounts
    total_all_due = fields.Monetary(
        compute='_compute_total_due',
        groups='account.group_account_readonly,account.group_account_invoice')
    total_all_due_abs = fields.Monetary(
        compute='_compute_total_due',
        groups='account.group_account_readonly,account.group_account_invoice')
    total_all_overdue = fields.Monetary(
        compute='_compute_total_due',
        groups='account.group_account_readonly,account.group_account_invoice')
    total_due = fields.Monetary(
        compute='_compute_total_due',
        groups='account.group_account_readonly,account.group_account_invoice')
    total_due_followup = fields.Monetary(
        compute='_compute_total_due',
        groups='account.group_account_readonly,account.group_account_invoice')
    total_due_currency_followup = fields.Monetary(
        compute='_compute_total_due',
        groups='account.group_account_readonly,account.group_account_invoice')
    total_overdue = fields.Monetary(
        compute='_compute_total_due',
        groups='account.group_account_readonly,account.group_account_invoice')
    total_overdue_followup = fields.Monetary(
        compute='_compute_total_due',
        groups='account.group_account_readonly,account.group_account_invoice')
    total_overdue_currency_followup = fields.Monetary(
        compute='_compute_total_due',
        groups='account.group_account_readonly,account.group_account_invoice')
    followup_single_currency_id = fields.Many2one(
        comodel_name='res.currency',
        compute='_compute_total_due',
    )
    followup_line_id = fields.Many2one(
        comodel_name='account_followup.followup.line',
        string="Reminder Level",
        compute='_compute_followup_line',
        search='_search_followup_line_id',
        groups='account.group_account_readonly,account.group_account_invoice',
    )
    has_moves = fields.Boolean(compute='_compute_has_moves')
    followup_responsible_id = fields.Many2one(
        comodel_name='res.users',
        string='Responsible',
        help="The responsible assigned to manual reminder activities, if defined in the level.",
        tracking=True,
        copy=False,
        company_dependent=True,
        groups='account.group_account_readonly,account.group_account_invoice',
    )

    @api.depends('invoice_ids.line_ids.no_followup')
    @api.depends_context('company', 'allowed_company_ids')
    def _compute_total_due(self):
        due_data = defaultdict(float)
        overdue_data = defaultdict(float)
        receivable_due_data = defaultdict(float)
        receivable_due_followup_data = defaultdict(float)
        receivable_due_currency_followup_data = defaultdict(float)
        receivable_overdue_data = defaultdict(float)
        receivable_overdue_followup_data = defaultdict(float)
        receivable_overdue_currency_followup_data = defaultdict(float)
        followup_single_currency_id = defaultdict()
        unreconciled_aml_ids = defaultdict(list)
        for account_type, overdue, partner, no_followup, amount_residual_sum, aml_ids, amount_residual_currency_sum, currency_ids in self.env['account.move.line']._read_group(
            domain=self._get_unreconciled_aml_domain(),
            groupby=['account_type', 'followup_overdue', 'partner_id', 'no_followup'],
            aggregates=['amount_residual:sum', 'id:array_agg', 'amount_residual_currency:sum', 'currency_id:array_agg'],
        ):
            if account_type == 'asset_receivable':
                unreconciled_aml_ids[partner] += aml_ids
                receivable_due_data[partner] += amount_residual_sum
                if not no_followup:
                    receivable_due_followup_data[partner] += amount_residual_sum
                    if len(set(currency_ids)) == 1:
                        receivable_due_currency_followup_data[partner] += amount_residual_currency_sum
                        followup_single_currency_id[partner] = currency_ids[0]
                if overdue:
                    receivable_overdue_data[partner] += amount_residual_sum
                    if not no_followup:
                        receivable_overdue_followup_data[partner] += amount_residual_sum
                        if len(set(currency_ids)) == 1:
                            receivable_overdue_currency_followup_data[partner] += amount_residual_currency_sum
                            followup_single_currency_id[partner] = currency_ids[0]

            due_data[partner] += amount_residual_sum
            if overdue:
                overdue_data[partner] += amount_residual_sum

        for partner in self:
            partner.total_all_due = due_data.get(partner, 0.0)
            partner.total_all_due_abs = abs(due_data.get(partner, 0.0))
            partner.total_all_overdue = overdue_data.get(partner, 0.0)
            partner.total_due = receivable_due_data.get(partner, 0.0)
            partner.total_due_followup = receivable_due_followup_data.get(partner, 0.0)
            partner.total_due_currency_followup = receivable_due_currency_followup_data.get(partner, 0.0)
            partner.total_overdue = receivable_overdue_data.get(partner, 0.0)
            partner.total_overdue_followup = receivable_overdue_followup_data.get(partner, 0.0)
            partner.total_overdue_currency_followup = receivable_overdue_currency_followup_data.get(partner, 0.0)
            partner.followup_single_currency_id = followup_single_currency_id.get(partner, False)
            partner.unreconciled_aml_ids = self.env['account.move.line'].browse(unreconciled_aml_ids.get(partner, []))

    @api.depends('invoice_ids.last_reminder')
    @api.depends_context('company')
    def _compute_last_reminder_date(self):
        moves = self.env['account.move']._read_group(
            domain=[
                ('partner_id', 'in', self.ids),
                ('last_reminder', '!=', False),
                ('company_id', '=', self.env.company.id),
            ],
            aggregates=['last_reminder:max'],
            groupby=['partner_id'],
        )
        moves_data = {partner.id: date for partner, date in moves}

        for partner in self:
            partner.last_reminder = moves_data.get(partner.id)

    @api.depends('invoice_ids.line_ids.followup_line_id', 'invoice_ids.line_ids.no_followup')
    @api.depends_context('company', 'allowed_company_ids')
    def _compute_followup_line(self):
        if not self.ids:
            self.followup_line_id = False
            return

        query = self._get_followup_open_invoices_query(self.ids)
        open_invoices = self.env.execute_query_dict(query)
        followup_lines = {row['partner_id']: row['followup_line_id'] for row in open_invoices}

        for partner in self:
            partner.followup_line_id = followup_lines.get(partner.id, False)

    def _search_followup_line_id(self, operator, value):
        if operator != 'in':
            return NotImplemented

        value_ids = list(value)

        if not value_ids:
            return Domain.FALSE

        query = SQL(
            """
                SELECT oi.partner_id
                FROM (%(open_invoices_query)s) oi
                WHERE oi.followup_line_id = ANY(%(line_ids)s)
            """,
            open_invoices_query=self._get_followup_open_invoices_query(),
            line_ids=value_ids,
        )

        return [('id', 'in', [r[0] for r in self.env.execute_query(query)])]

    @api.depends('company_id')
    @api.depends_context('company')
    def _compute_automatic_invoice_reminder(self):
        self.automatic_invoice_reminder = self.env.company.automatic_invoice_reminder

    def _get_unreconciled_aml_domain(self):
        return Domain.AND([
            Domain('reconciled', '=', False),
            Domain('account_id.account_type', 'in', ('asset_receivable', 'liability_payable')),
            Domain('parent_state', '=', 'posted'),
            Domain('partner_id', 'in', self.ids),
            Domain('company_id', 'child_of', self.env.company.id),
        ])

    def _get_followup_responsible(self, multiple_responsible=False, *, followup_line=None):
        self.ensure_one()

        if not followup_line:
            followup_line = self.followup_line_id

        responsible_type = followup_line.activity_default_responsible_type
        if responsible_type == 'account_manager' and self.user_id:
            return self.user_id

        all_aml_responsible = self.unreconciled_aml_ids.move_id.invoice_user_id
        max_amount_aml = max(
            self.unreconciled_aml_ids.filtered('move_id.invoice_user_id'),
            default=self.env['account.move.line'],
            key=lambda l: l.amount_residual,
        )
        candidates = [
            (responsible_type == 'salesperson' and (
                all_aml_responsible if multiple_responsible else max_amount_aml.move_id.invoice_user_id
            )),
            self.followup_responsible_id,
            self.user_id,
            max_amount_aml.move_id.invoice_user_id,
        ]
        return next((u for u in candidates if u and u.filtered('active')), super()._get_followup_responsible(multiple_responsible=multiple_responsible, followup_line=followup_line))

    def _get_all_followup_contacts(self):
        """ Followup contacts are defined as billing address and defaults to
        contact as defined in 'address_get' """
        self.ensure_one()
        return self.env['res.partner'].browse(self.address_get(['invoice'])['invoice'])

    def _get_invoices_to_print(self, options):
        self.ensure_one()
        invoices_to_print = self.unreconciled_aml_ids.filtered(
            lambda aml: not aml.no_followup and aml.followup_line_id.delay <= options['followup_line'].delay
        ).move_id.filtered(lambda move: move.is_invoice(include_receipts=True))
        return invoices_to_print.filtered(lambda inv: inv.invoice_pdf_report_id)

    def send_followup_email(self, options):
        """
        Send a follow-up report by email to customers in self
        """
        for record in self:
            options['partner_id'] = record.id
            self.env['account.followup.report']._send_email(options)

    def send_followup_sms(self, options):
        """
        Send a follow-up report by sms to customers in self
        """
        for partner in self:
            options['partner_id'] = partner.id
            self.env['account.followup.report']._send_sms(options)

    def get_followup_html(self, options=None):
        """
        Return the content of the follow-up report in HTML
        """
        if options is None:
            options = {}
        options.update({
            'partner_id': self.id,
            'followup_line_id': self.followup_line_id,
        })
        return self.env['account.followup.report'].with_context(print_mode=True, lang=self.lang or self.env.user.lang).get_followup_report_html(options)

    def _get_all_followup_data(self):
        if 'res_partner_all_followup' in self.env.cr.cache:
            return self.env.cr.cache['res_partner_all_followup']

        # Put the data in a cache in the cursor to avoid running costly query multiple times in same transaction.
        # Only do it if the table doesn't exist yet.
        query = self._get_followup_data_query()
        self.env.cr.cache['res_partner_all_followup'] = {
            r['partner_id']: r for r in self.env.execute_query_dict(query)
        }
        return self.env.cr.cache['res_partner_all_followup']

    def _query_followup_data(self, all_partners=False):
        if all_partners:
            return self._get_all_followup_data()
        if not self.ids:
            return {}
        if 'res_partner_all_followup' in self.env.cr.cache:
            cache_dict = self.env.cr.cache['res_partner_all_followup']
            return {id_: cache_dict[id_] for id_ in self.ids if id_ in cache_dict}
        query = self._get_followup_data_query(self.ids)
        return {r['partner_id']: r for r in self.env.execute_query_dict(query)}

    def _get_followup_open_invoices_query(self, partner_ids=None):
        self.env['account.move.line'].check_access('read')
        self.env['account.move.line'].flush_model()
        self.env['res.partner'].flush_model()
        self.env['account_followup.followup.line'].flush_model()
        return SQL(
            """
                SELECT DISTINCT ON (aml.partner_id)
                    aml.id AS aml_id,
                    aml.partner_id,
                    aml.account_id,
                    aml.move_id,
                    aml.company_id,
                    aml.date_maturity,
                    aml.followup_line_id,
                    aml.name
                FROM account_move_line aml
                INNER JOIN account_account account ON account.id = aml.account_id
                INNER JOIN res_partner p ON p.id = aml.partner_id
                WHERE account.account_type = 'asset_receivable'
                  AND p.followup_reminder_type = 'automatic'
                  AND aml.parent_state = 'posted'
                  AND aml.reconciled IS NOT TRUE
                  AND aml.amount_residual > 0
                  AND aml.no_followup IS NOT TRUE
                  AND aml.date_maturity IS NOT NULL
                %(partner_filter)s
                AND aml.company_id = ANY(%(company_ids)s)
                ORDER BY aml.partner_id, aml.date_maturity, aml.create_date, aml.id ASC
            """,
            partner_filter=SQL("AND aml.partner_id = ANY(%s)", partner_ids) if partner_ids else SQL(""),
            company_ids=self.env.companies.ids,
        )

    def _get_followup_data_query(self, partner_ids=None):
        """Build an SQL query to fetch the lowest applicable reminder level per partner
        based on the most overdue receivable move line and the reminder delay conditions.

        When updating reminder levels, we only track the most overdue unreconciled
        receivable move line for each partner.

        We always send the lowest applicable reminder level. There are three cases:

        - An eligible move line that has not yet received any reminders receives its first reminder immediately.
        - A move line whose reminders have been sent on schedule receives the next reminder based on its maturity date and the current date.
        - A move line whose reminders were not sent on schedule (belated) receives the next reminder based on its `last_auto_reminder` value.
        """
        return SQL(
            """
            SELECT
                oi.aml_id,
                oi.partner_id,
                fl.delay,
                fl.id AS followup_line_id
            FROM (%(open_invoices_query)s) oi
            LEFT JOIN account_move am ON am.id = oi.move_id
            LEFT JOIN account_followup_followup_line current_fl ON current_fl.id = oi.followup_line_id and current_fl.company_id = oi.company_id
            JOIN LATERAL (
                SELECT fl.id, fl.delay
                FROM account_followup_followup_line fl
                WHERE fl.company_id = oi.company_id
                  AND (
                      ( -- previous reminder sent
                        am.last_auto_reminder IS NOT NULL
                        AND current_fl.id IS NOT NULL
                        AND fl.delay > current_fl.delay
                        AND fl.delay <= %(current_date)s - GREATEST(oi.date_maturity, am.last_auto_reminder - current_fl.delay)
                        )
                      OR ( -- no reminders sent yet
                        current_fl.id IS NULL
                        AND fl.delay <= %(current_date)s - oi.date_maturity
                      )
                  )
                ORDER BY fl.delay ASC
                LIMIT 1
            ) fl ON TRUE
            ORDER BY oi.partner_id;
            """,
            open_invoices_query=self._get_followup_open_invoices_query(partner_ids),
            current_date=fields.Date.context_today(self),
        )

    def _send_followup(self, options):
        """ Send the follow-up to the partner, depending on selected options.
        Can be overridden to include more ways of sending the follow-up.
        """
        self.ensure_one()
        followup_line = options.get('followup_line')
        if options.get('email', followup_line.send_email):
            self.send_followup_email(options)
        if options.get('sms', followup_line.send_sms):
            self.send_followup_sms(options)

    def _get_followup_report(self, options):
        followup_report = self.env.ref('account_reports.followup_report')
        options = followup_report.get_options({
            'forced_companies': self.env.company.search([('id', 'child_of', self.env.context.get('allowed_company_ids', self.env.company.id))]).ids,
            'partner_ids': self.ids,
            'unfold_all': True,
            'unreconciled': True,
            'all_entries': False,
            'export_mode': 'print',
        })
        return self._get_partner_account_report_attachment(followup_report, options=options).id

    def _get_followup_attachments(self, options):
        res_attachment_ids = []
        followup_line = options.get('followup_line')

        # Add the Follow-up report
        options['report_attachment_id'] = self._get_followup_report(options)
        res_attachment_ids.append(options['report_attachment_id'])

        # Add the attachments from the template
        if template_id := options.get('template_id', followup_line.mail_template_id):
            template_attachments = template_id._generate_template_attachments(self.ids, {'attachment_ids', 'report_template_ids'})[self.id]
            res_attachment_ids += template_attachments['attachment_ids']

            attachments_to_create = [
                {
                    'name': dynamic_report[0],
                    'raw': dynamic_report[1],
                    'res_model': self._name,
                    'res_id': self.id,
                }
                for dynamic_report in template_attachments['attachments']
            ]
            res_attachment_ids += self.env['ir.attachment'].create(attachments_to_create).ids
        # Add the PDFs from invoices
        res_attachment_ids += self._get_invoices_to_print({'followup_line': followup_line}).invoice_pdf_report_id.ids
        return res_attachment_ids

    def _execute_followup_partner(self, options):
        """ Execute the actions to do with follow-ups for this partner (apart from printing).
        This is called for automatic follow-ups (cron). Automatic follow-ups can also be
        triggered manually with *action_manually_process_automatic_followups*.
        'followup_line' should be provided in options.
        """
        self.ensure_one()

        followup_line = options.get('followup_line')
        aml = options.get('aml')
        today = fields.Date.context_today(self)

        aml.followup_line_id = followup_line
        aml.move_id.write({
            'last_reminder': today,
            'last_auto_reminder': today,
        })

        if followup_line.create_activity:
            # log a next activity for today
            for user in self._get_followup_responsible(multiple_responsible=True, followup_line=followup_line):
                self.activity_schedule(
                    activity_type_id=followup_line.activity_type_id.id or self._default_activity_type().id,
                    note=followup_line.activity_note,
                    summary=followup_line.activity_summary,
                    user_id=user.id,
                )

        options['attachment_ids'] = self._get_followup_attachments(options)
        self._send_followup(options)

    def _create_followup_missing_information_wizard(self):
        """ Returns a wizard containing all the partners with missing information.
        """

        return {
            'type': 'ir.actions.act_window',
            'name': _("Missing information"),
            'view_mode': 'form',
            'res_model': 'account_followup.missing.information.wizard',
            'target': 'new',
            'context': {'default_partner_ids': self.ids},
        }

    def _has_missing_followup_info(self, followup_line):
        self.ensure_one()

        followup_contacts = self._get_all_followup_contacts() or self

        return (
            (followup_line.send_email and not any(followup_contacts.mapped('email'))) or
            (followup_line.send_sms and not any(followup_contacts.mapped('phone')))
        )

    def action_manually_process_automatic_followups(self):
        partners_with_missing_info = self.env['res.partner']
        followup_data = self._query_followup_data()

        partner_ids_to_process = {partner['partner_id'] for partner in followup_data.values()}
        for partner in self:
            if partner.id not in partner_ids_to_process:
                continue
            followup_line_id = followup_data[partner.id]['followup_line_id']
            aml_id = followup_data[partner.id]['aml_id']

            followup_line = self.env['account_followup.followup.line'].browse(followup_line_id)
            aml = self.env['account.move.line'].browse(aml_id)

            # Skip partner with missing info.
            if partner._has_missing_followup_info(followup_line):
                partners_with_missing_info |= partner
                continue
            partner._execute_followup_partner({'followup_line': followup_line, 'aml': aml})

        # If one or more partners are missing information, open a wizard listing them.
        if partners_with_missing_info:
            return partners_with_missing_info._create_followup_missing_information_wizard()
        return None

    def _cron_execute_followup_company(self, batch_size=1000):
        """Execute pending followups for the current company.
        :param batch_size: maximum number of followup to process
        :return: Return True if all followup were processed, False otherwise
        :rtype: boolean
        """
        followup_data = self._query_followup_data(all_partners=True)
        partners = self.env['res.partner'].browse([d['partner_id'] for d in followup_data.values()])
        for partner in partners[:batch_size]:
            if partner.followup_next_action_date and partner.followup_next_action_date >= fields.Date.context_today(self):
                continue

            followup_line_id = followup_data[partner.id]['followup_line_id']
            aml_id = followup_data[partner.id]['aml_id']
            followup_line = self.env['account_followup.followup.line'].browse(followup_line_id)
            aml = self.env['account.move.line'].browse(aml_id)
            try:
                partner._execute_followup_partner({'followup_line': followup_line, 'aml': aml})
            except UserError as e:
                # followup may raise exception due to configuration issues
                # i.e. partner missing email
                partner._message_log(body=e)
                _logger.warning(e, exc_info=True)
        return bool(not partners[batch_size:])

    def _cron_execute_followup(self, batch_size=1000):
        """Execute pending followups for all companies.
        :param batch_size: maximum number of followup to process for each company
        """
        all_companies = self.env["res.company"].search([('automatic_invoice_reminder', '=', True)])
        self.env["ir.cron"]._commit_progress(remaining=len(all_companies))
        unfinished = 0
        for company in all_companies:
            # Since the cache is done by database and not by company, we need to invalidate in this special case
            # where the context is changing in the same transaction
            self.env.cr.cache.pop('res_partner_all_followup', None)
            all_done = self.with_context(allowed_company_ids=company.ids)._cron_execute_followup_company(batch_size=batch_size)
            if not all_done:
                unfinished += 1
            self.env["ir.cron"]._commit_progress(1)
        if unfinished:
            # if not all followups could be processed, let the cron be retriggered
            self.env["ir.cron"]._commit_progress(remaining=unfinished)

    def _show_pay_now_button(self):
        invoice_online_payment = self.env['ir.config_parameter'].sudo().get_bool('account_payment.enable_portal_payment')
        payment_method_available = bool('payment.method' in self.env and self.env['payment.method'].sudo().search_count([('active', '=', True)]))
        partner_has_user = bool(self.user_ids)
        return invoice_online_payment and payment_method_available and partner_has_user

    def _compute_has_moves(self):
        field_names = ['partner_id', 'partner_shipping_id', 'commercial_partner_id']
        partner_ids = {row[0] for row in self.env.execute_query(SQL("\nUNION ").join(
            [self.env['account.move']._search(
                [('company_id', 'in', self.env.companies.ids), (name, 'in', self.ids)]
            ).subselect(SQL.identifier('account_move', name)) for name in field_names] +
            [self.env['account.move.line']._search(
                [('company_id', 'in', self.env.companies.ids), ('partner_id', 'in', self.ids)]
            ).subselect(SQL('account_move_line.partner_id'))]
        ))}

        for partner in self:
            partner.has_moves = partner.id in partner_ids

    def _get_followup_report_pdf(self, options):
        """
        Generate the Reminder report and return a tuple (filename, pdf_bin).
        """
        tz_date_str = format_date(self.env, fields.Date.today(), lang_code=self.env.user.lang or get_lang(self.env).code)
        # To avoid having dots in the name of the file.
        tz_date_str = tz_date_str.replace('.', '-')
        followup_letter_name = _("Follow-up %(partner)s - %(date)s.pdf", partner=self.display_name, date=tz_date_str)

        action = self.env.ref('account_followup.action_report_followup')
        followup_letter = action.with_context(lang=self.lang or self.env.user.lang)._render_qweb_pdf('account_followup.report_followup_print_all', self.id, data={'options': options or {}})[0]

        return followup_letter_name, followup_letter
