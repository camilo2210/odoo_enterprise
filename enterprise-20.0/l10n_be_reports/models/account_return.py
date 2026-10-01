import json

from markupsafe import Markup

from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import format_date
from odoo.tools.translate import LazyTranslate
import ast

_lt = LazyTranslate(__name__)


class AccountReturnType(models.Model):
    _inherit = 'account.return.type'

    def _get_start_date_elements(self, main_company):
        return super()._get_start_date_elements(main_company)


class AccountReturn(models.Model):
    _inherit = 'account.return'

    l10n_be_submission_error = fields.Text(copy=False, readonly=True)
    l10n_be_isoc_mute_buttons = fields.Boolean(compute="_compute_l10n_be_isoc_mute_buttons")

    l10n_be_isoc_payment_form_id = fields.Many2one(
        string="Isoc form",
        comodel_name='l10n_be_reports.isoc.prepayment.pay.form',
    )

    @api.depends('type_external_id', 'l10n_be_isoc_payment_form_id.currency_id', 'l10n_be_isoc_payment_form_id.amount_to_pay')
    def _compute_l10n_be_isoc_mute_buttons(self):
        for account_return in self:
            if account_return.type_external_id == 'l10n_be_reports.be_isoc_prepayment_return_type' and account_return.l10n_be_isoc_payment_form_id:
                account_return.l10n_be_isoc_mute_buttons = account_return.l10n_be_isoc_payment_form_id.currency_id.is_zero(account_return.l10n_be_isoc_payment_form_id.amount_to_pay)
            else:
                account_return.l10n_be_isoc_mute_buttons = True

    @api.model_create_multi
    def create(self, vals_list):
        returns = super().create(vals_list)
        returns_type_ext_ids = set(returns.mapped('type_external_id'))
        if 'l10n_be_reports.be_vat_return_type' in returns_type_ext_ids:
            if partner_fps_belgium := self.env.ref('l10n_be_reports.partner_fps_belgium', raise_if_not_found=False):
                partner_fps_belgium.active = True
        if 'l10n_be_reports.be_isoc_prepayment_return_type' in returns_type_ext_ids:
            if partner_centre_de_perception_belgium := self.env.ref('l10n_be_reports.partner_centre_de_perception_belgium', raise_if_not_found=False):
                partner_centre_de_perception_belgium.active = True
        return returns

    @api.model
    def _evaluate_deadline(self, company, return_type, return_type_external_id, date_from, date_to):
        months_per_period = return_type._get_periodicity_months_delay(company)
        if return_type.with_company(company).deadline_days_delay:
            pass

        elif return_type_external_id in ('l10n_be_reports.be_vat_return_type', 'l10n_be_reports.be_ec_sales_list_return_type') and months_per_period in (1, 3):
            # https://finances.belgium.be/fr/entreprises/tva/calendrier-tva#q1
            return date_to + relativedelta(days=20 if months_per_period == 1 else 25)

        elif return_type_external_id == 'l10n_be_reports.be_vat_listing_return_type':
            return date_to + relativedelta(months=3)

        elif return_type_external_id == 'l10n_be_reports.be_isoc_prepayment_return_type':
            return date_to + relativedelta(days=-9 if date_to.month == 12 else 10)

        elif return_type_external_id == 'account_reports.annual_corporate_tax_return_type' and company.account_fiscal_country_id.code == 'BE':
            return date_to + relativedelta(months=7)

        return super()._evaluate_deadline(company, return_type, return_type_external_id, date_from, date_to)

    def _get_pay_wizard(self):
        if self.type_external_id == 'l10n_be_reports.be_vat_return_type':
            # If the amount is to be recovered, we don't want to open the wizard and just continue to the next state
            if self.amount_to_pay_currency_id.compare_amounts(self.total_amount_to_pay, 0) == -1:
                return

            # Check that we use the right bank account (change on 2026-05-01)
            pivot_date = fields.Date.from_string('2026-04-01')
            old_bank_account = 'BE22679200300047'  # 'VAT Current Account': Bank account BEFORE April 2026
            new_bank_account = 'BE41679200364210'  # 'VAT Provision Account': Bank account AFTER April 2026
            bank_accounts = self.env['res.partner.bank'].search([
                ('active', '=', True),
                ('sanitized_account_number', 'in', [old_bank_account, new_bank_account]),
            ])
            account_number = old_bank_account if self.date_to < pivot_date else new_bank_account
            fps_account = bank_accounts.filtered(lambda bank: bank.sanitized_account_number == account_number)
            if not fps_account:
                fps_partner = (
                        bank_accounts.partner_id
                        or self.env.ref('l10n_be_reports.partner_fps_belgium', raise_if_not_found=False)
                        or self.env['res.partner'].create({'name': 'VAT Revenue Services'})
                )
                fps_account = self.env['res.partner.bank'].create({
                    'partner_id': fps_partner.id,
                    'account_number': account_number,
                    'allow_out_payment': True,
                })
            self.type_id.payment_partner_bank_id = fps_account

            vat_pay_wizard = self.env['l10n_be_reports.vat.pay.wizard'].create([{
                'company_id': self.company_id.id,
                'partner_bank_id': self.type_id.payment_partner_bank_id.id,
                'currency_id': self.amount_to_pay_currency_id.id,
                'return_id': self.id,
            }])

            return {
                'type': 'ir.actions.act_window',
                'name': _("VAT Payment"),
                'res_model': 'l10n_be_reports.vat.pay.wizard',
                'res_id': vat_pay_wizard.id,
                'views': [(False, 'form')],
                'target': 'new',
            }

        return super()._get_pay_wizard()

    def _get_checks_kanban_view_id(self):
        self.ensure_one()
        if self.type_external_id == 'l10n_be_reports.be_isoc_prepayment_return_type':
            return self.env.ref('l10n_be_reports.account_return_check_kanban_view').id

        return super()._get_checks_kanban_view_id()

    def _run_checks(self, check_codes_to_ignore):
        checks = super()._run_checks(check_codes_to_ignore)

        if self.type_external_id == 'l10n_be_reports.be_isoc_prepayment_return_type':
            if self.l10n_be_isoc_payment_form_id:
                if not self.is_completed:
                    # Updating fields that might change if the return is not completed.
                    # If the return is completed, those fields stay locked to the old values on purpose for history
                    self.l10n_be_isoc_payment_form_id.partner_bank_id = self.type_id.payment_partner_bank_id
                    self.l10n_be_isoc_payment_form_id.currency_id = self.amount_to_pay_currency_id
                return checks

            create_vals = {
                'company_id': self.company_id.id,
                'partner_bank_id': self.type_id.payment_partner_bank_id.id,
                'currency_id': self.amount_to_pay_currency_id.id,
                'return_id': self.id,
            }

            previous_return = self.env['account.return'].search([
                ('type_id', '=', self.type_id.id),
                ('date_to', '<', self.date_from),
                ('company_id', '=', self.company_id.id),
                ('company_ids', 'in', self.company_ids.ids),
                ('is_completed', '=', True),
                ('l10n_be_isoc_payment_form_id', '!=', False),
            ], order="date_to desc", limit=1)
            if previous_return:
                create_vals['amount_to_pay'] = previous_return.l10n_be_isoc_payment_form_id.amount_to_pay
                create_vals['profit_estimate'] = previous_return.l10n_be_isoc_payment_form_id.profit_estimate
                create_vals['corporate_tax_rate'] = previous_return.l10n_be_isoc_payment_form_id.corporate_tax_rate

            self.l10n_be_isoc_payment_form_id = self.env['l10n_be_reports.isoc.prepayment.pay.form'].create(create_vals)

        if self.type_external_id == 'l10n_be_reports.be_vat_return_type':
            checks += self._check_suite_be_tax_report_vat(check_codes_to_ignore)

        if self.type_external_id == 'l10n_be_reports.be_vat_listing_return_type':
            checks += self._check_suite_be_partner_vat_listing(check_codes_to_ignore)

        return checks

    def _check_suite_be_tax_report_vat(self, check_codes_to_ignore):
        checks = []
        report = self.type_id.report_id
        if 'be_vat_compliance' not in check_codes_to_ignore:

            options = self._get_closing_report_options()
            warnings = {}

            report._get_lines(options, all_column_groups_expression_totals=None, warnings=warnings)
            submission_warnings = 'l10n_be_reports.tax_report_warning_checks' in warnings

            if submission_warnings:
                action = {
                    'type': 'ir.actions.client',
                    'name': _("VAT Report (BE)"),
                    'tag': 'account_report',
                    'context': {'report_id': self.type_id.report_id.id},
                    'params': {
                        'options': options,
                        'ignore_session': True,
                    }
                }

                checks.append({
                    'name': _lt("Intervat Validation"),
                    'message': _lt("A validation rule failed. Intervat may reject your VAT report. Open the report to view the warning."),
                    'code': 'be_vat_compliance',
                    'action': action,
                    'result': 'anomaly',
                })

        if 'be_vat_deductibility' not in check_codes_to_ignore:
            checks.append({
                'name': _lt("Tax codes & deductibility"),
                'message': _lt(
                    "Vendor bills with restricted deductions (cars, restaurants, gifts, etc.) should use a tax that "
                    "splits the amount correctly, sending the deductible portion to the VAT Recoverable grid. "
                    "Also check that all tax codes set on your invoices and bills are correct."
                ),
                'code': 'be_vat_deductibility',
                'result': 'todo',
            })

        return checks

    def _check_suite_be_partner_vat_listing(self, check_codes_to_ignore):
        checks = []
        if 'sales_threshold' not in check_codes_to_ignore:
            # The report always ensures that though SQL, so the test can never fail; we still add it to reassure the user
            checks.append({
                'name': _lt("Sales above 250€"),
                'message': _lt("Only include customers with total annual taxable sales exceeding 250€ (excluding VAT) or a credit note."),
                'code': 'sales_threshold',
                'result': 'reviewed',
            })

        if 'customer_without_country' not in check_codes_to_ignore:
            domain = [
                ('company_id', 'in', self.company_ids.ids),
                ('date', '<=', fields.Date.to_string(self.date_to)),
                ('date', '>=', fields.Date.to_string(self.date_from)),
                ('state', '=', 'posted'),
                ('partner_id.country_id', '=', False),
                ('move_type', 'in', self.env['account.move'].get_sale_types()),
            ]
            no_country_moves_count = self.env['account.move'].search_count(domain, limit=21)
            action = {
                'type': 'ir.actions.act_window',
                'name': _("Invoices Without Country"),
                'view_mode': 'list',
                'res_model': 'account.move',
                'domain': domain,
                'views': [[False, 'list'], [False, 'form']],
            }
            check_vals = {
                'name': _lt("No customer without country"),
                'message': _lt("Review invoices having a customer with no country specified."),
                'code': 'customer_without_country',
                'records_count': no_country_moves_count,
                'records_model': self.env['ir.model']._get('account.move').id,
                'result': 'anomaly' if no_country_moves_count else 'reviewed',
                'action': action if no_country_moves_count else False,
            }

            checks.append(check_vals)

        return checks

    def action_reset_tax_return_common(self):
        if self.type_external_id == 'l10n_be_reports.be_vat_return_type':
            self.write({'l10n_be_submission_error': False})
        return super().action_reset_tax_return_common()

    def _prepare_submission(self):
        # OVERRIDE
        self._check_all_branches_allowed()
        if self.type_external_id == 'l10n_be_reports.be_vat_return_type':
            if self.company_id.l10n_be_intervat_mode != 'disabled':
                if not self.company_id._l10n_be_intervat_is_authentication_valid():
                    return self.company_id._l10n_be_intervat_authentication_action(self.id, 'submit')
                return self._l10n_be_submit_xml()
            return self.env['l10n_be_reports.vat.return.submission.wizard']._open_submission_wizard(self)

        if self.type_external_id == 'account_reports.annual_corporate_tax_return_type' and self.company_id.account_fiscal_country_id.code == 'BE':
            return self.env['l10n_be_reports.annual.corporate.tax.submission.wizard']._open_submission_wizard(
                self,
                instructions=_("""
                    <p>
                        Once your accounting year is closed, it's time to think about corporate income tax (ISOC).<br/>
                        Here's the key info in 4 simple steps:
                    </p>
                    <ol>
                        <li>Year-end = the countdown starts. You have 7 months to file your ISOC return via <a href="https://finances.belgium.be/fr/E-services/biztax" target="new">Biztax</a>.</li>
                        <li>Your profit is taxed at 20% or 25%, depending on your company's status and the amount of profit.</li>
                        <li>Any advance tax payments (prepayments) you've made will be automatically deducted from the total tax due.</li>
                        <li>Overpaid? You get a refund. Underpaid? You'll need to pay the balance (and possibly a surcharge).</li>
                    </ol>
                """)
            )

        if self.type_external_id == 'l10n_be_reports.be_vat_listing_return_type':
            return self.env['l10n_be_reports.vat.listing.submission.wizard']._open_submission_wizard(self)

        if self.type_external_id == 'l10n_be_reports.be_ec_sales_list_return_type':
            return self.env['l10n_be_reports.ec.sales.list.submission.wizard']._open_submission_wizard(self)

        return super()._prepare_submission()

    def action_be_isoc_mark_paid(self):
        self.ensure_one()
        return self.l10n_be_isoc_payment_form_id.action_mark_as_paid()

    def action_be_isoc_send_email(self):
        self.ensure_one()
        template = self.env.ref('l10n_be_reports.email_template_vai_payment_instructions', raise_if_not_found=False)
        return self.action_send_email_instructions(self.l10n_be_isoc_payment_form_id, template)

    def _generate_locking_attachments(self, options):
        super()._generate_locking_attachments(options)
        if self.type_external_id == 'l10n_be_reports.be_vat_listing_return_type':
            self._add_attachment(self.type_id.report_id.dispatch_report_action(options, 'partner_vat_listing_export_to_xml'))
        elif self.type_external_id == 'l10n_be_reports.be_ec_sales_list_return_type':
            self._add_attachment(self.type_id.report_id.dispatch_report_action(options, 'export_to_xml_sales_report'))

    def l10n_be_reset_tax_prepayment(self):
        self.ensure_one()

        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(_("Only an Accounting Administrator can reset a tax return"))

        if self.state == 'paid':
            self._reset_checks_for_states([self.state, False])
            self.state = False

        self.is_completed = False

        return True

    def l10n_be_action_fetch_from_intervat(self):
        if not self.company_id._l10n_be_intervat_is_authentication_valid():
            return self.company_id._l10n_be_intervat_authentication_action(self.id, 'fetch')

        options = self._get_closing_report_options()
        options['return_id'] = self.id

        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'model': self.env.context.get('model'),
                'options': json.dumps(options),
                'file_generator': 'generate_zip_file_from_intervat',
            }
        }

    def _l10n_be_submit_xml(self):
        self.write({'l10n_be_submission_error': False})
        att = next(a for a in self.attachment_ids if a.res_name == self.name and a.name.endswith('.xml'))
        try:
            response = self.company_id._l10n_be_post_vat_declaration(att.raw.content, att.name)
        except UserError as e:
            self.write({'l10n_be_submission_error': e.args[0]})
            self._message_log(body=self.env._("Submission Error: \n") + e.args[0])
            self.env.user._bus_send('simple_notification', {
                'type': 'danger',
                'title': self.env._("Submission Error"),
                'message': e.args[0],
            })
            return 'error'

        if response is None:
            return self.company_id._l10n_be_intervat_authentication_action(self.id, 'submit')

        # We create a new declaration object, so we will be able to fetch the linked documents from
        # MyMinfin API
        new_declaration = self.env['l10n_be.vat.declaration'].create([{
            'pdf_ref': response['pdfReference'],
            'xml_ref': response['xmlReference'],
            'return_id': self.id,
        }])

        # We mark the previous declaration as rectified
        self.env['l10n_be.vat.declaration'].search([
            ('id', '!=', new_declaration.id),
            ('return_id', '=', self.id),
            ('rectification_declaration_id', '=', False),
        ], limit=1).rectification_declaration_id = new_declaration

        self._message_log(body=Markup("""\
        <p>
            %(msg)s:
            <li><strong>PDF</strong>: %(pdf_ref)s</li>
            <li><strong>XML</strong>: %(xml_ref)s</li>
        </p>""") % {
            'msg': self.env._(
                "VAT return of period %(date_from)s -> %(date_to)s has been sent with the following references",
                date_from=Markup("<strong>%s</strong>") % format_date(self.env, self.date_from),
                date_to=Markup("<strong>%s</strong>") % format_date(self.env, self.date_to),
            ),
            'pdf_ref': response['pdfReference'],
            'xml_ref': response['xmlReference'],
        })

        return self._proceed_with_submission()

    def _compute_visible_states(self):
        super()._compute_visible_states()
        for record in self:
            if record.type_external_id == 'l10n_be_reports.be_vat_return_type':
                if record.state not in {'submitted', 'paid'} and record.l10n_be_submission_error:
                    new_visible_states = []
                    for state_data in record.visible_states:
                        if state_data['name'] == 'submitted':
                            state_data['alert_type'] = 'danger'
                            state_data['error_msg'] = record.l10n_be_submission_error
                        new_visible_states.append(state_data)
                    record.visible_states = new_visible_states


class AccountReturnCheck(models.Model):
    _inherit = 'account.return.check'

    @api.model
    def action_audit_custom_target(self, audit_id, target):
        def get_account_balances_action(account_prefixes):
            action = self.env['ir.actions.act_window']._for_xml_id('account_reports.action_view_account_balances')
            action['context'] = {
                'working_file_id': audit_id,
                'search_default_l10n_be_audit_accounts': 1,
                **{f'l10n_be_audit_acc_{i + 1}': prefix for i, prefix in enumerate(account_prefixes)}
            }
            return action

        def get_action_dict(action_xml_id):
            action_ref = action_xml_id and self.env.ref(action_xml_id, raise_if_not_found=False)
            if action_ref:
                return action_ref._get_action_dict()
            return False

        if action := super().action_audit_custom_target(audit_id, target):
            return action

        if not audit_id:
            return False
        audit = self.env['account.return'].browse(audit_id)
        if audit.type_external_id != 'l10n_be_reports.l10n_be_audit_return_type':
            return False

        if target == 'depreciation_schedule':
            if action := self.action_audit_report(audit_id, 'account_asset.action_account_report_assets'):
                return action
            return get_account_balances_action(['20%', '21%', '22%', '23%', '24%', '25%'])

        if target == 'inventory_valuation':
            if action := get_action_dict('account.action_report_stock_valuation'):
                action['params'] = {
                    'date_to': audit.date_to,
                }
                return action
            return get_account_balances_action(['3%', '60%'])

        if target == 'fleet':
            if action := get_action_dict('fleet.fleet_vehicle_action'):
                if self.env.user.has_group('fleet.group_fleet_user'):
                    return action
            return get_account_balances_action(['20%', '21%', '22%', '23%', '24%', '25%'])

        if target == 'documents':
            if self.env.ref('documents.document_action', raise_if_not_found=False) and self.env.user.has_group('documents.group_documents_user'):
                return {
                    'type': 'ir.actions.act_url',
                    'url': f'{self.get_base_url()}/odoo/documents',
                    'target': 'new',
                }
            journal_line_action = get_action_dict('account.action_move_journal_line')
            journal_line_action['domain'] = [
                ('date', '>=', audit.date_from),
                ('date', '<=', audit.date_to),
                ('company_id', 'in', audit.company_ids.ids),
            ]
            return journal_line_action

        if target == 'product_margin':
            if self.env.ref('base.module_product_margin').state == 'installed' and self.env.user.has_group('account.group_account_user'):
                product_margin = self.env['product.margin'].create({
                    'from_date': audit.date_from,
                    'to_date': audit.date_to,
                })
                return product_margin.action_open_window()
            return get_account_balances_action(['3%'])

        if target == 'invoices_to_be_issued':
            if action := get_action_dict('sale_account_accountant.sale_order_line_accrual_to_bill_action'):
                ctx = ast.literal_eval(action['context'])
                ctx.pop('search_default_last_365_days')
                ctx['accrual_entry_date'] = audit.date_to
                action['context'] = ctx
                return action
            journal_line_action = get_action_dict('account.action_move_journal_line')
            journal_line_action['domain'] = [
                ('date', '>=', audit.date_from),
                ('date', '<=', audit.date_to),
                ('company_id', 'in', audit.company_ids.ids),
            ]
            return journal_line_action

        return False
