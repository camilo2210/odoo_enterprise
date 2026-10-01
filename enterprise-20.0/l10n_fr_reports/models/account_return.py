from odoo import _, api, fields, models
from odoo.tools.translate import LazyTranslate

_lt = LazyTranslate(__name__)


class AccountReturn(models.Model):
    _inherit = 'account.return'

    l10n_fr_reports_export = fields.Many2one('account.report.async.export', compute='_compute_l10n_fr_reports_export')

    def _compute_l10n_fr_reports_export(self):
        exports = self.env['account.report.async.export'].search([('return_id', 'in', self.ids)]).grouped('return_id')
        for account_return in self:
            account_return.l10n_fr_reports_export = exports.get(account_return, False)

    def _postprocess_vat_closing_entry_results(self, company, options, results):
        # OVERRIDE
        """ Apply the rounding from the French tax report by adding a line to the end of the query results
            representing the sum of the roundings on each line of the tax report.
        """
        if self.type_external_id == 'l10n_fr_reports.vat_return_type':
            rounding_accounts = {
                'profit': company.l10n_fr_rounding_difference_profit_account_id,
                'loss': company.l10n_fr_rounding_difference_loss_account_id,
            }

            vat_results_summary = [
                ('due', self.env.ref('l10n_fr_account.tax_report_32').id, 'balance'),
                ('due', self.env.ref('l10n_fr_account.tax_report_22').id, 'balance'),
                ('deductible', self.env.ref('l10n_fr_account.tax_report_27').id, 'balance'),
            ]
            return self._vat_closing_entry_results_rounding(company, options, results, rounding_accounts, vat_results_summary)

        return super()._postprocess_vat_closing_entry_results(company, options, results)

    def _get_company_required_fields(self):
        fields = super()._get_company_required_fields()
        if self.company_id.country_id.code == 'FR':
            fields.append(self.company_id.l10n_fr_rof_type)
        return fields

    def _prepare_submission(self):
        # EXTENDS account_reports
        if self.type_external_id == 'l10n_fr_reports.vat_return_type':
            bank_partner_ids = self.env['res.partner.bank'].search([('partner_id', '=', self.company_id.partner_id.id), ('partner_id.country_code', '=', 'FR')])
            context = {
                'default_report_id': self.type_id.report_id.id,
                'default_return_id': self.id,
                'default_company_id': self.company_id.id,
                'default_bank_partner_id': bank_partner_ids.id if len(bank_partner_ids) == 1 else False,
                'default_date_from': self.date_from,
                'default_date_to': self.date_to,
            }
            return self.env['l10n_fr_reports.send.vat.report'].with_context(**context)._get_records_action(name=_("EDI VAT"), target='new')

        if self.type_external_id == 'l10n_fr_reports.das2_return_type':
            l10n_fr_das2_report = self.env['l10n_fr.send.das2.report'].create({
                'return_id': self.id,
                'year': str(self.date_to.year),
            })
            return l10n_fr_das2_report._get_records_action(name=self.env._("DAS2 Report"), target='new', res_id=l10n_fr_das2_report.id)

        if self.type_external_id == 'l10n_fr_reports.l10n_fr_fiscal_declaration_return_type':
            if self.company_id.l10n_fr_fiscal_regime == 'normal':
                return self.env['l10n_fr_reports.aspone.sso.wizard']._action_redirect(self.company_id)

            l10n_fr_fiscal_declaration = self.env['l10n_fr_reports.send.fiscal.declaration'].create({
                'report_id': self.type_id.report_id.id,
                'return_id': self.id,
                'company_id': self.company_id.id,
                'date_from': self.date_from,
                'date_to': self.date_to,
            })
            return l10n_fr_fiscal_declaration._get_records_action(name=self.env._("Fiscal Declaration"), target='new', res_id=l10n_fr_fiscal_declaration.id)

        return super()._prepare_submission()

    def action_reset_tax_return_common(self):
        """ Extends of account report to remove the external value if we reset a submitted return.
            This external value is created when the locking move is created.
        """
        # EXTENDS account_reports
        self.ensure_one()
        if self.state == 'submitted' and self.company_id.account_fiscal_country_id.code == 'FR':
            external_values = self.env['account.report.external.value'].search([
                ('date', '=', self.date_to),
                ('target_report_expression_id', 'in', {
                    self.env.ref('l10n_fr_account.tax_report_26_external_tag', raise_if_not_found=False).id,
                    self.env.ref('l10n_fr_account.tax_report_22_applied_carryover', raise_if_not_found=False).id,
                }),
            ])
            external_values.unlink()

        return super().action_reset_tax_return_common()

    def action_view_export(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("EDI VAT"),
            'res_model': 'account.report.async.export',
            'views': [(self.env.ref('l10n_fr_reports.view_account_report_async_export_form').id, 'form')],
            'res_id': self.l10n_fr_reports_export.id,
        }

    def _compute_visible_states(self):
        super()._compute_visible_states()
        return_records = self.filtered(lambda r: r.type_external_id in {
            'l10n_fr_reports.vat_return_type',
            'l10n_fr_reports.das2_return_type',
            'l10n_fr_reports.l10n_fr_fiscal_declaration_return_type',
        })
        if not return_records:
            return
        domain = [
            ('report_id', 'in', return_records.mapped('type_id.report_id').ids),
            ('date_from', 'in', return_records.mapped('date_from')),
            ('date_to', 'in', return_records.mapped('date_to')),
        ]
        candidate_exports = self.env['account.report.async.export'].search(domain, order='create_date desc')
        export_map = {}
        for export in candidate_exports:
            key = (export.report_id.id, export.date_from, export.date_to)
            if key not in export_map:
                export_map[key] = export
        for record in return_records:
            key = (record.type_id.report_id.id, record.date_from, record.date_to)
            last_export = export_map.get(key)
            if last_export and record.state != 'submitted' and last_export.create_date < record.write_date:
                last_export = False

            alert_type = False
            status_msg = False

            if last_export:
                selection_dict = dict(last_export._fields['recipient']._description_selection(self.env))
                recipient_name = selection_dict.get(last_export.recipient) or 'DGFiP'
                if last_export.state == 'rejected':
                    alert_type = 'danger'
                    status_msg = self.env._("Rejected by %s", recipient_name)
                elif last_export.state == 'accepted':
                    alert_type = 'success'
                    status_msg = self.env._("Accepted by %s", recipient_name)
                elif last_export.state in {'sent', 'to_send'}:
                    alert_type = 'warning'
                    status_msg = self.env._("Pending / Sent to %s", recipient_name)

            if alert_type:
                new_visible_states = []
                for state_data in record.visible_states:
                    if state_data['name'] == 'submitted':
                        state_data['alert_type'] = alert_type
                        state_data['error_msg'] = status_msg
                    new_visible_states.append(state_data)
                record.visible_states = new_visible_states

    @api.model
    def _l10n_fr_reports_build_check_vals(self, *, name, message, code, records_model, records_count, result, action):
        return {
            'name': name,
            'message': message,
            'code': code,
            'records_count': records_count,
            'records_model': self.env['ir.model']._get(records_model).id,
            'result': result,
            'action': action,
        }

    @api.model
    def _l10n_fr_reports_build_partners_with_missing_information(self, checks, invalid_records, message, anomaly):
        required_field_view_list = self.env.ref('l10n_fr_reports.view_partner_das2_required_partner_fields')
        required_field_view_form = self.env.ref('l10n_fr_reports.view_partner_form_inherit_das2_required_partner_fields')
        action = self.env['res.partner']._get_records_action(
            name=self.env._("Partners with missing information"),
            domain=[('id', 'in', invalid_records.ids)],
            views=[(required_field_view_list.id, 'list'), (required_field_view_form.id, 'form')],
        )
        checks.append(self._l10n_fr_reports_build_check_vals(
            name=_lt("Partners with missing information"),
            message=message,
            code='partners_with_missing_information',
            records_model='res.partner',
            records_count=len(invalid_records),
            result='anomaly' if anomaly else 'reviewed',
            action=action,
        ))

    @api.model
    def _run_das2_checks(self, check_codes_to_ignore):
        checks = []
        partners = self.env['res.partner'].search([
            *self.env['res.partner']._check_company_domain(self.company_id),
            ('l10n_fr_profession_id', '!=', False),
            ('invoice_ids', 'any', [('country_code', '=', 'FR'), ('state', '=', 'posted')]),
        ])
        contact_person = self.env.user.partner_id  # we use the contact_person's default value (current user) as a precaution
        error_data = self.env['l10n_fr.das2.report.handler']._check_required_fields(partners, contact_person)

        if 'partners_with_missing_information' not in check_codes_to_ignore and (partner_errors := error_data['partner']['errors']):
            self._l10n_fr_reports_build_partners_with_missing_information(
                checks=checks,
                invalid_records=error_data['partner']['records'],
                message=_lt("Review partners having missing information."),
                anomaly=partner_errors,
            )

        if 'no_accounts_with_das2_tags' not in check_codes_to_ignore:
            das2_tags = self.env['l10n_fr.das2.report.handler']._get_das2_tags()
            accounts_with_das2_tags_exist = self.env['account.account'].search_count([
                ('tag_ids', 'in', das2_tags.ids),
            ], limit=1)

            if not accounts_with_das2_tags_exist:
                action = self.env['account.account']._get_records_action(
                    name=_("Accounts with DAS2 tags"),
                    views=[[False, 'list'], [False, 'form']],
                )
                checks.append(self._l10n_fr_reports_build_check_vals(
                    name=_lt("At least one account with DAS2 tags"),
                    message=_lt("Add DAS2 tags to at least one account."),
                    code='no_accounts_with_das2_tags',
                    records_model='account.account',
                    records_count=0,
                    result='anomaly',
                    action=action,
                ))

        missing_info_specs = [
            (
                'company_with_missing_information',
                _lt("Company with missing information"),
                _lt("Company with missing information"),
                _lt("Review the company's missing information."),
                'res.company',
                error_data['company'],
                'l10n_fr_reports.view_company_form_inherit_das2_required_fields',
            ),
            (
                'account_representative_with_missing_information',
                _lt("Account Representative with missing information"),
                _lt("Account Representative with missing information"),
                _lt("Review the Account Representative's missing information."),
                'res.partner',
                error_data['account_representative'],
                'l10n_fr_reports.view_partner_form_inherit_das2_required_firm_fields',
            ),
            (
                'contact_person_with_missing_information',
                _lt("Contact Person with missing information"),
                _lt("Default contact person with missing information"),
                _lt("Review the Contact Person's missing information."),
                'res.partner',
                error_data['contact_person'],
                'l10n_fr_reports.view_partner_form_inherit_das2_required_contact_person_fields',
            ),
        ]

        for code, action_name, check_name, message, model, data, view_id in missing_info_specs:
            if code in check_codes_to_ignore or not data['errors']:
                continue

            required_field_view_form = self.env.ref(view_id)
            action = self.env[model]._get_records_action(
                name=action_name,
                res_id=data['record'].id,
                views=[(required_field_view_form.id, 'form')],
            )
            checks.append(self._l10n_fr_reports_build_check_vals(
                name=check_name,
                message=message,
                code=code,
                records_model=model,
                records_count=1,
                result='anomaly',
                action=action,
            ))

        return checks

    @api.model
    def _run_fiscal_declaration_checks(self, check_codes_to_ignore):
        checks = []
        error_data = self.env['l10n_fr_reports.fiscal_declaration_handler']._check_required_fields(self._get_closing_report_options())

        if 'debtor_with_missing_information' not in check_codes_to_ignore and (debtor := error_data['debtor']['record']):
            debtor_errors = error_data['debtor']['errors']
            action = debtor._get_records_action(
                name=self.env._("Missing informations on the Company"),
                views=[(self.env.ref('l10n_fr_reports.view_company_form_inherit_das2_required_fields').id, 'form')],
            )
            checks.append(self._l10n_fr_reports_build_check_vals(
                name=_lt("Company with missing information"),
                message=_lt("Review the company's missing information. Make sure that both the address and company registry are accurately completed."),
                code='debtor_with_missing_information',
                records_model='res.company',
                records_count=1,
                result='anomaly' if debtor_errors else 'reviewed',
                action=action,
            ))

        if 'writer_with_missing_information' not in check_codes_to_ignore and (writer := error_data['writer']['record']):
            writer_errors = error_data['writer']['errors']
            action = writer._get_records_action(
                name=self.env._("Partners with missing information"),
                views=[(self.env.ref('l10n_fr_reports.view_partner_form_inherit_das2_required_firm_fields').id, 'form')],
            )
            checks.append(self._l10n_fr_reports_build_check_vals(
                name=_lt("Account Representative with missing information"),
                message=_lt("Review the Account Representative's missing information."),
                code='writer_with_missing_information',
                records_model='res.partner',
                records_count=1,
                result='anomaly' if writer_errors else 'reviewed',
                action=action,
            ))

        if 'partners_with_missing_information' not in check_codes_to_ignore:
            self._l10n_fr_reports_build_partners_with_missing_information(
                checks=checks,
                invalid_records=error_data['partners']['records'],
                message=_lt("Review partners having missing information. For addresses, simply enter ' / ' for non-address required fields."),
                anomaly=error_data['partners']['errors'],
            )

        return checks

    def _run_checks(self, check_codes_to_ignore):
        checks = super()._run_checks(check_codes_to_ignore)

        if self.type_external_id == 'l10n_fr_reports.das2_return_type':
            checks += self._run_das2_checks(check_codes_to_ignore) or []
        elif self.type_external_id == 'l10n_fr_reports.l10n_fr_fiscal_declaration_return_type':
            checks += self._run_fiscal_declaration_checks(check_codes_to_ignore) or []

        return checks

    def _get_carryover_accounts_to_balance(self, key):
        # EXTENDS account_reports
        accounts = super()._get_carryover_accounts_to_balance(key)
        if self.type_external_id == 'l10n_fr_reports.vat_return_type':
            accounts.append((key[1], self.env._('Balance tax current account (receivable)')))
        return accounts
