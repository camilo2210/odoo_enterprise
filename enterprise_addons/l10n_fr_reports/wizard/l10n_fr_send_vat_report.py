import re

from odoo import api, Command, fields, models, _
from odoo.tools import BinaryBytes, cleanup_xml_node, float_repr, float_compare, format_date
from odoo.exceptions import ValidationError, UserError, RedirectWarning

from lxml import etree
from stdnum.fr import siret

CODE_TO_EDI_ID = {
    'box_A1': 'CA',
    'box_A2': 'CB',
    'box_A3': 'KH',
    'box_A4': 'DK',
    'box_A5': 'KV',
    'box_B1': 'CH',
    'box_B2': 'CC',
    'box_B3': 'CF',
    'box_B4': 'CG',
    'box_B5': 'CE',
    'box_E1': 'DA',
    'box_E2': 'DB',
    'box_E3': 'DH',
    'box_E4': 'KW',
    'box_E5': 'KX',
    'box_E6': 'KY',
    'box_F1': 'KZ',
    'box_F2': 'DC',
    'box_F3': 'DF',
    'box_F4': 'DJ',
    'box_F5': 'LA',
    'box_F6': 'DD',
    'box_F7': 'DG',
    'box_F8': 'DE',
    'box_F9': 'LR',
    'box_08_base': 'FP',
    'box_08_taxe': 'GP',
    'box_09_base': 'FB',
    'box_09_taxe': 'GB',
    'box_9B_base': 'FR',
    'box_9B_taxe': 'GR',
    'box_10_base': 'FM',
    'box_10_taxe': 'GM',
    'box_11_base': 'FN',
    'box_11_taxe': 'GN',
    'box_T1_base': 'BQ',
    'box_T1_taxe': 'CQ',
    'box_T2_base': 'BP',
    'box_T2_taxe': 'CP',
    'box_T3_base': 'BS',
    'box_T3_taxe': 'CS',
    'box_T4_base': 'BF',
    'box_T4_taxe': 'MC',
    'box_T5_base': 'BE',
    'box_T5_taxe': 'MA',
    'box_T6_base': 'MF',
    'box_T6_taxe': 'ME',
    'box_T7_base': 'MG',
    'box_T7_taxe': 'MD',
    'box_13_base': 'FC',
    'box_13_taxe': 'GC',
    'box_P1_base': 'GS',
    'box_P1_taxe': 'GT',
    'box_P2_base': 'GU',
    'box_P2_taxe': 'GV',
    'box_I1_base': 'LB',
    'box_I1_taxe': 'LC',
    'box_I2_base': 'LD',
    'box_I2_taxe': 'LE',
    'box_I3_base': 'LF',
    'box_I3_taxe': 'LG',
    'box_I4_base': 'LH',
    'box_I4_taxe': 'LJ',
    'box_I5_base': 'LK',
    'box_I5_taxe': 'LL',
    'box_I6_base': 'LM',
    'box_I6_taxe': 'LN',
    'box_15': 'GG',
    'box_15_1': 'GA',
    'box_15_2': 'LQ',
    'box_5B': 'KS',
    'box_16': 'GH',
    'box_17': 'GJ',
    'box_18': 'GK',
    'box_19': 'HA',
    'box_20': 'HB',
    'box_21': 'HC',
    'box_22': 'HD',
    'box_2C': 'KU',
    'box_22A': 'HE',
    'box_23': 'HG',
    'box_24': 'HF',
    'box_2E': 'HL',
    'box_25': 'JA',
    'box_TD': 'KA',
    'box_26_external': 'JB',
    'box_AA': 'KJ',
    'box_27': 'JC',
    'box_Y5': 'MT',
    'box_Y6': 'MH',
    'box_X5': 'MN',
    'box_28': 'ND',
    'box_29': 'KB',
    'box_Z5': 'NC',
    'box_AB': 'KL',
    'box_32': 'KE',
}

REIMBURSEMENT_TYPE_MAPPING = {
    'first_asking': {'code': 'DI', 'date_code': 'DL'},
    'assignment_cessation': {'code': 'DJ', 'date_code': 'DM'},
    'others': {'code': 'DK', 'date_code': None},
}

# Specific Lines (not filled if 0):
# * 22A: the tax coefficient and cannot be 0
# * P1 and P2: petroleum lines and should be sent only for companies with specific tax regimes
# * F9: should be in the xml only for vat units
# * A4, I1, I2, I3, I4, I5: some companies do not have the option to declare VAT import
LINES_CODE_NOT_FILLED_IF_0 = {
    'box_A4', 'box_F9', 'box_I1_base', 'box_I2_base', 'box_I3_base', 'box_I4_base', 'box_I5_base',
    'box_I6_base', 'box_22A', 'box_P1_base', 'box_P1_taxe', 'box_P2_base', 'box_P2_taxe',
}

BIC_REGEX = re.compile(r'[A-Z0-9]{8}|[A-Z0-9]{11}')


class L10n_Fr_ReportsSendVatReport(models.TransientModel):
    _name = 'l10n_fr_reports.send.vat.report'
    _description = "Send VAT Report Wizard"

    recipient = fields.Selection([
        ("DGI_EDI_TVA", "DGFiP"),
        ("CEC_EDI_TVA", "Expert Accountant"),
        ("OGA_EDI_TVA", "OGA"),
    ], default="DGI_EDI_TVA", required=True)
    company_partner_id = fields.Many2one(
        comodel_name='res.partner',
        related='company_id.partner_id',
    )
    bank_partner_id = fields.Many2one(
        comodel_name='res.partner.bank',
        domain="[('partner_id', '=', company_partner_id), ('partner_id.country_code', '=', 'FR')]",
    )
    has_wrongly_configured_account = fields.Boolean(compute='_compute_has_wrongly_configured_account')
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    report_id = fields.Many2one(
        comodel_name='account.report',
        required=True,
    )
    return_id = fields.Many2one(
        comodel_name='account.return',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        default=lambda self: self.env.company,
    )
    l10n_fr_rof_type = fields.Integer(
        string="ROF",
        related='company_id.l10n_fr_rof_type',
        readonly=False,
    )
    is_vat_due = fields.Boolean(compute='_compute_vat_amount')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    use_partial_amount = fields.Boolean()
    partial_amount = fields.Monetary('Partial amount')
    vat_amount = fields.Monetary(compute='_compute_vat_amount')
    computed_vat_amount = fields.Monetary(compute='_compute_computed_vat_amount')
    is_reimbursement_comment = fields.Boolean(string="Add reimbursement comment")
    reimbursement_comment = fields.Text()
    reimbursement_date = fields.Date(string="Date", default=fields.Date.today())
    reimbursement_type = fields.Selection(
        string="Reimbursement type",
        selection=[
            ('first_asking', "First asking"),
            ('assignment_cessation', "Assignment, cessation, death, entry into a VAT group"),
            ('others', "Others"),
        ],
        default='first_asking',
    )
    show_express_mention = fields.Boolean()
    express_mention_reason = fields.Text()
    report_async_document_ids = fields.Many2many(comodel_name='account.report.async.document', relation='report_document_fr_send_vat_report_rel')

    @api.depends('report_id', 'date_from', 'date_to')
    def _compute_vat_amount(self):
        vat_carried_forward_line = self.env.ref('l10n_fr_account.tax_report_27')
        vat_payable_line = self.env.ref('l10n_fr_account.tax_report_32')
        result_vat_lines = (vat_carried_forward_line + vat_payable_line)
        for wizard in self:
            wizard.vat_amount = 0
            wizard.is_vat_due = False
            if not wizard.date_from or not wizard.date_to or not wizard.report_id:
                continue
            options = wizard.report_id.get_options({'no_format': True, 'date': {'date_from': wizard.date_from, 'date_to': wizard.date_to}, 'unfold_all': True})
            lines = wizard.report_id._get_lines(options)
            column_value = 0
            report_line_id = 0
            # Looking for the line that have data (either the VAT credit or the VAT due)
            # Only one of these lines could have a value, not both of them.
            for line in lines:
                report_line_id = wizard.report_id._get_model_info_from_id(line.id)[-1]
                if report_line_id in result_vat_lines.ids:
                    column = next(col for col in line.columns if col.expression_label == 'balance')
                    column_value = column.no_format or 0
                    if column_value:
                        break

            wizard.vat_amount = column_value
            wizard.is_vat_due = result_vat_lines.filtered(lambda line: line.id == report_line_id).code == vat_payable_line.code

    @api.depends('use_partial_amount', 'partial_amount', 'vat_amount')
    def _compute_computed_vat_amount(self):
        for wizard in self:
            wizard.computed_vat_amount = wizard.partial_amount if wizard.use_partial_amount else wizard.vat_amount

    @api.depends('bank_partner_id', 'bank_partner_id.account_number', 'bank_partner_id.bank_bic')
    def _compute_has_wrongly_configured_account(self):
        for wizard in self:
            wizard.has_wrongly_configured_account = wizard.bank_partner_id and not wizard._check_bank_account_line()

    def _check_bank_account_line(self):
        self.ensure_one()

        iban = (self.bank_partner_id.account_number or '').replace(' ', '')
        bic = (self.bank_partner_id.bank_bic or '').replace(' ', '')
        return self._validate_iban(iban) and BIC_REGEX.fullmatch(bic)

    @api.model
    def _validate_iban(self, iban):
        # Move the four initial characters to the end of the string
        temp_iban = iban[4:] + iban[:4]

        # Replace each letter with two digit (A = 10, b = 11, ...)
        replaced_iban = ""
        for i in temp_iban:
            replaced_iban += i if i.isnumeric() else str(ord(i.upper()) - 55)
        # Take the whole and apply modulo 97, it should be 1
        return int(replaced_iban) % 97 == 1

    def _get_address_dict(self, company):
        return {
            'street': company.street[:30],
            'complement': f"{company.street[30:]} {company.street2 or ''}".strip()[:35],
            'postal_code': company.zip[:17],
            'city': company.city[:35],
            'country_code': company.country_id.code,
        }

    def _check_constraints(self, model, list_fields):
        error_list = []
        for field in list_fields:
            if not model[field]:
                error_list.append(_("%(field)s is required on %(model)s", field=model._fields[field].string, model=model.display_name))
        if error_list:
            raise ValidationError(", ".join(error_list))

    def _check_siret(self, company):
        if not siret.is_valid(company.l10n_fr_siret):
            raise ValidationError(_("%(company)s has an invalid siret: %(siret)s.", company=company.display_name, siret=company.l10n_fr_siret))

    def _check_bank_account(self):
        self.ensure_one()
        if self.has_wrongly_configured_account:
            raise UserError(_("The selected bank account should have an IBAN and a bic code."))

    def _check_vat_to_pay(self):
        self.ensure_one()
        if self.use_partial_amount and float_compare(self.partial_amount, 0, precision_digits=self.currency_id.decimal_places) <= 0:
            raise UserError(_("You can't set an amount with a negative value or a value set to 0."))

    def _check_values_export(self, options):
        # Check constraints
        sender_company = self.report_id._get_sender_company_for_export(options)
        # Assume Emitor = Writer -> omit the emitor
        writer = sender_company.account_representative_id or sender_company
        self._check_constraints(writer, ['l10n_fr_siret', 'street', 'zip', 'city', 'country_id'])
        self._check_siret(writer)
        # Debtor
        debtor = sender_company
        self._check_constraints(debtor, ['l10n_fr_siret', 'street', 'zip', 'city', 'country_id'])
        self._check_siret(debtor)

        self._check_bank_account()
        self._check_vat_to_pay()

    def _get_formatted_edi_values(self, lines):
        edi_values = []

        self.express_mention_reason = (self.express_mention_reason or "").strip()
        if self.express_mention_reason:
            edi_values.extend(self._get_express_mention())

        report_lines_code_per_id = {line['id']: line['code'] for line in self.report_id.line_ids.read(['id', 'code'])}
        for line in lines:
            model, report_line_id = self.report_id._get_model_info_from_id(line.id)
            if model != 'account.report.line':
                continue
            report_line_code = report_lines_code_per_id[report_line_id]
            if edi_id := CODE_TO_EDI_ID.get(report_line_code):
                column = next(col for col in line.columns if col.expression_label == 'balance')
                column_value = column.no_format or 0
                if report_line_code in LINES_CODE_NOT_FILLED_IF_0 and self.currency_id.is_zero(column_value):
                    continue
                edi_values.append({
                    'id': edi_id,
                    'value': float_repr(self.currency_id.round(column_value), self.currency_id.decimal_places).replace('.', ','),
                })

        if self.currency_id.is_zero(self.vat_amount):
            edi_values.append({
                'id': "KF",
                'value': "X",
            })

        return edi_values

    def _get_formatted_payment_values(self):
        self.ensure_one()
        if not self.bank_partner_id.account_number or not self.bank_partner_id.bank_bic:
            return []
        return [
            {
                'id': 'GA',
                'iban': self.bank_partner_id.account_number.replace(' ', ''),
                'bic': self.bank_partner_id.bank_bic.replace(' ', ''),
            },
            {
                'id': 'HA',
                'value': float_repr(
                    self.currency_id.round(self.computed_vat_amount),
                    self.currency_id.decimal_places,
                ).replace('.', ','),
            },
            {
                'id': 'KA',
                'value': f'TVA{self.l10n_fr_rof_type}-{self.date_from.strftime("%Y%m%d")}-{self.date_to.strftime("%Y%m%d")}-3310CA3',
            },
        ]

    def _get_express_mention(self):
        self.ensure_one()
        return [
            {
                'id': 'BA',
                'ftx_1': self.express_mention_reason,
            },
            {
                'id': 'BC',
                'value': 'X',
            },
        ]

    def _get_common_edi_vals(self, options):
        sender_company = self.report_id._get_sender_company_for_export(options)
        # Assume Emitor = Writer -> omit the emitor
        writer = sender_company.account_representative_id or sender_company
        debtor = sender_company
        writer_vals = {
            'siret': writer.l10n_fr_siret.replace(" ", ""),
            'designation': "CEC_EDI_TVA",
            'designation_cont_1': writer.name[:35],  # "raison sociale"
            'designation_cont_2': writer.name[35:70],  # "raison sociale"
            'address': self._get_address_dict(writer),
        }
        debtor_vals = {
            'identifier': debtor.l10n_fr_siren.replace(" ", ""),
            'designation': debtor.name[:35],  # "raison sociale"
            'address': self._get_address_dict(debtor),
            'rof': f'TVA{self.l10n_fr_rof_type}',  # "référence obligation fiscale"
        }
        # EDI partner
        edi_partner_vals = {
            'identifier': '4200001',
            'designation': 'TESSI INFORMATIQUE',
            'address': {
                'number': 7,
                'street': 'PARC METROTECH',
                'postal_code': 42650,
                'city': 'SAINT-JEAN-BONNEFONDS',
                'country_code': 'FR',
            },
            'reference': 'DEC00001',
        }
        # T-IDENTIF
        identif_vals = [
            {
                'id': 'AA',
                'identifier': debtor.l10n_fr_siren.replace(" ", ""),
                'designation': debtor.display_name[:35],
                'address': self._get_address_dict(debtor),
            },
            {'id': 'KD', 'value': f'TVA{self.l10n_fr_rof_type}'},  # ROF
            {'id': 'CA', 'value': self.date_from.strftime("%Y%m%d")},  # declaration period: yyyymmdd
            {'id': 'CB', 'value': self.date_to.strftime("%Y%m%d")},
        ]
        return writer_vals, debtor_vals, edi_partner_vals, identif_vals

    def _prepare_edi_vals(self, options, lines):
        edi_values = self._get_formatted_edi_values(lines)
        if not edi_values:
            raise UserError(_("The tax report is empty."))

        writer_vals, debtor_vals, edi_partner_vals, identif_vals = self._get_common_edi_vals(options)

        if self.is_vat_due:
            identif_vals.extend(self._get_formatted_payment_values())
        is_neutralized = self.env['ir.config_parameter'].sudo().get_bool('database.is_neutralized')

        return {
            'date_from': self.date_from.strftime("%Y%m%d"),
            'date_to': self.date_to.strftime("%Y%m%d"),
            'is_test': '1' if self._is_test_env() or is_neutralized else '0',
            'type': "INFENT",
            'declarations': [{
                'type': "IDT",  # depends on the procedure
                'reference': "INFENT000042",  # internal reference to the emitor
                'writer': writer_vals,
                'debtor': debtor_vals,
                'edi_partner': edi_partner_vals,
                'recipients': [{'designation': self.recipient}],
                # T-IDENTIF form
                'identif': {
                    'millesime': "26",
                    'zones': identif_vals,
                },
                # 3310CA3
                'forms': [{
                    'millesime': "26",
                    'name': "3310CA3",
                    'zones': edi_values,
                }]
            }],
        }

    def _create_carryover_reimbursment_move(self, options):
        """ Creates an account.move representing the carryover reimbursement.

            This move debits the receivable accounts from the present tax group in the VAT
            closing entry for the period selected in the report options and moves the amount
            to a special account. The special account is used to track the reimbursement
            requested from the administration.

            :param options: dict - Report options for the VAT period selection.
            :return: account.move - Represents the carryover reimbursement.
        """
        account_return = self.env['account.return']._get_return_from_report_options(options)
        tax_closing_entry = account_return.closing_move_ids if account_return else None
        if not tax_closing_entry:
            raise RedirectWarning(
                _("No closing entry was found. Please create one it before sending your report."),
                self.env['account.return'].action_open_tax_return_view(additional_return_domain=[
                    ('date_to', '<=', options['date']['date_to']),
                    ('date_from', '>=', options['date']['date_from']),
                    ('type_id.report_id', '=', options['report_id']),
                ]),
                _("Create Closing Entry"),
            )

        _payable_accounts, tax_receivable_account_ids = account_return._get_tax_closing_payable_and_receivable_accounts()
        tax_carried_forward_line_ids = tax_closing_entry.line_ids.filtered(
            lambda line: line.account_id in tax_receivable_account_ids and line.name != _('Balance tax current account (receivable)')
        )

        lines = []
        if amount_carried_forward := sum(tax_carried_forward_line_ids.mapped('balance')):
            ratio = self.computed_vat_amount / amount_carried_forward
            for tax_line in tax_carried_forward_line_ids:
                lines.append(Command.create({
                    'account_id': tax_line.account_id.id,
                    'debit': 0,
                    'credit': tax_line.balance * ratio,
                    'name': _("VAT receivable"),
                }))
        else:
            # Case where tax closing is empty for this month while amount is carried forward from previous months
            # We put the amount on the receivable account the return settles on
            lines.append(Command.create({
                'account_id': tax_receivable_account_ids[:1].id,
                'debit': 0,
                'credit': self.computed_vat_amount,
                'name': _("VAT receivable"),
            }))

        return self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': tax_closing_entry.journal_id.id,
            'date': self.date_to,
            'line_ids': [
                *lines,
                Command.create({
                    'account_id': self.env['account.chart.template'].ref('pcg_44583').id,
                    'debit': self.computed_vat_amount,
                    'credit': 0,
                }),
            ],
        })

    @api.model
    def _get_vat_report_name(self, date_from, date_to):
        date_from = date_from.strftime("%m/%Y")
        date_to = date_to.strftime("%m/%Y")
        if date_from != date_to:
            return _("TaxReport_%(date_from)s-%(date_to)s", date_from=date_from, date_to=date_to)
        return _("TaxReport_%(date_from)s", date_from=date_from)

    def _is_test_env(self):
        return self.env['account.report.async.document']._is_aspone_test_mode()

    def send_vat_return(self):
        self.ensure_one()

        if (self.is_vat_due or self.is_reimbursement_comment) and not self.bank_partner_id:
            raise UserError(self.env._("A bank account is needed to send this VAT return."))
        if self.has_wrongly_configured_account:
            raise UserError(self.env._("The chosen bank account needs to have a BIC and an account number set up."))

        options = self.report_id.get_options(
            {'no_format': True, 'date': {'date_from': self.date_from, 'date_to': self.date_to}, 'unfold_all': True})
        self._check_values_export(options)

        lines = self.report_id._get_lines(options)

        # Generate xml
        vals = self._prepare_edi_vals(options, lines)
        xml_content = self.env['ir.qweb']._render('l10n_fr_reports.aspone_xml_edi', vals)
        try:
            xml_content.encode('ISO-8859-15')
        except UnicodeEncodeError as e:
            raise ValidationError(
                _("The xml file generated contains an invalid character: '%s'", xml_content[e.start:e.end]))

        xml_content = etree.tostring(cleanup_xml_node(xml_content), encoding='ISO-8859-15', standalone='yes')

        if self._check_duplicate_vat_declaration(self.date_from, self.date_to, self.recipient, xml_content):
            raise UserError(self.env._("For the period %(date_from)s to %(date_to)s, a duplicate declaration exist.", date_from=self.date_from, date_to=self.date_to))

        if not self.is_vat_due and self.computed_vat_amount:
            if external_value_26 := self.env.ref('l10n_fr_account.tax_report_26_external_tag',
                                                 raise_if_not_found=False):
                # xml_id in module l10n_fr_account may not be updated yet
                self.env['account.report.external.value'].with_context(ignore_tax_lock_date=True).create({
                    'name': _(
                        "Carryover reimbursement from %(date_from)s to %(date_to)s",
                        date_from=format_date(self.env, self.date_from),
                        date_to=format_date(self.env, self.date_to)
                    ),
                    'value': self.computed_vat_amount,
                    'date': self.date_to,
                    'target_report_expression_id': external_value_26.id,
                    'company_id': self.env.company.id,
                })
            origin_expression = self.env.ref('l10n_fr_account.tax_report_27_carryover')
            self.env['account.report.external.value'].with_context(ignore_tax_lock_date=True).create({
                'name': _(
                    "Carryover reimbursement from %(date_from)s to %(date_to)s",
                    date_from=format_date(self.env, self.date_from),
                    date_to=format_date(self.env, self.date_to)
                ),
                'value': -self.computed_vat_amount,
                'date': self.date_to,
                'target_report_expression_id': self.env.ref('l10n_fr_account.tax_report_22_applied_carryover').id,
                'carryover_origin_expression_label': origin_expression.label,
                'carryover_origin_report_line_id': origin_expression.report_line_id.id,
                'company_id': self.env.company.id,
            })

            carryover_reimbursment_move = self._create_carryover_reimbursment_move(options)
            if not self._is_test_env():
                carryover_reimbursment_move._post()

            self._send_reimbursement_xml_to_aspone(options)
            # As we added the external values, we need to regenerate the pdf with the right values
            self.return_id.attachment_ids.filtered(lambda att: att.res_name == self.return_id.name and att.name.endswith('.pdf')).unlink()
            self.return_id._generate_locking_attachments(options)

        # Send xml to ASPOne
        vat_report_name = self._get_vat_report_name(self.date_from, self.date_to)
        self._send_xml_to_aspone(xml_content, vat_report_name)

        self.env['account.report.async.export'].create({
            'name': vat_report_name,
            'document_ids': [Command.set(self.report_async_document_ids.ids)],
            'date_from': self.date_from,
            'date_to': self.date_to,
            'report_id': self.env.ref('l10n_fr_account.tax_report').id,
            'recipient': self.recipient,
            'company_id': self.company_id.id,
            'return_id': self.return_id.id,
        })

    def _send_reimbursement_xml_to_aspone(self, options):
        """ Create declaration 3519 for the reimbursement asked on the bank account and send it to AspOne"""
        if not self.bank_partner_id:
            return
        writer_vals, debtor_vals, edi_partner_vals, identif_vals = self._get_common_edi_vals(options)
        sender_company = self.report_id._get_sender_company_for_export(options)

        is_neutralized = self.env['ir.config_parameter'].sudo().get_bool('database.is_neutralized')

        if sender_company.country_code == 'FR':
            company_location_code = 'DD'
        elif sender_company.country_id in self.env.ref('base.europe').country_ids:
            company_location_code = 'DE'
        else:
            company_location_code = 'DF'

        reimbursement_type_data = REIMBURSEMENT_TYPE_MAPPING.get(self.reimbursement_type)
        zones = [{
            'id': 'AA',
            'iban': self.bank_partner_id.account_number.replace(' ', ''),
            'bic': self.bank_partner_id.bank_bic.replace(' ', ''),
            'holder_name': self.bank_partner_id.holder_name[:35],
            'holder_name_2': self.bank_partner_id.holder_name[35:70],
        }, {
            'id': 'FK',
            'value': 'X',
        }, {
            'id': 'DN',
            'value': float_repr(
                self.currency_id.round(self.computed_vat_amount),
                self.currency_id.decimal_places,
            ).replace('.', ','),
        }, {
            'id': company_location_code,
            'value': 'X',
        }]
        # Add reimbursement type and date
        if reimbursement_type_data and reimbursement_type_data['code']:
            zones.append({'id': reimbursement_type_data['code'], 'value': 'X'})
        if reimbursement_type_data['date_code'] and self.reimbursement_date:
            zones.append({
                'id': reimbursement_type_data['date_code'],
                'value': self.reimbursement_date.strftime("%Y%m%d"),
            })
        if self.is_reimbursement_comment and self.reimbursement_comment:
            zones.append({'id': 'FJ', 'ftx_1': self.reimbursement_comment})

        declarations = {
            'type': 'RBT',
            'reference': "INFENT000042",  # internal reference to the emitor
            'writer': writer_vals,
            'debtor': debtor_vals,
            'edi_partner': edi_partner_vals,
            'recipients': [{'designation': self.recipient}],
            # T-IDENTIF form
            'identif': {
                'millesime': "26",
                'zones': identif_vals,
            },
            # 3519
            'forms': [{
                'millesime': "26",
                'name': "3519",
                'zones': zones,
            }],
        }

        vals = {
            'date_from': self.date_from.strftime("%Y%m%d"),
            'date_to': self.date_to.strftime("%Y%m%d"),
            'is_test': '1' if self._is_test_env() or is_neutralized else '0',
            'type': "INFENT",
            'declarations': [declarations],
        }

        xml_content = self.env['ir.qweb']._render('l10n_fr_reports.aspone_xml_edi', vals)
        try:
            xml_content.encode('ISO-8859-15')
        except UnicodeEncodeError as e:
            raise ValidationError(
                _("The xml file generated contains an invalid character: '%s'", xml_content[e.start:e.end]))

        xml_content = etree.tostring(cleanup_xml_node(xml_content), encoding='ISO-8859-15', standalone='yes')
        report_common_name = self._get_vat_report_name(self.date_from, self.date_to)
        reimbursement_name = _('%(report_common_name)s_reimbursement',
                                report_common_name=report_common_name)
        self._send_xml_to_aspone(xml_content, reimbursement_name)

    def _send_xml_to_aspone(self, xml_content, export_name):
        db_uuid = self.env['ir.config_parameter'].sudo().get_str('database.uuid')
        endpoint = self.env['account.report.async.document']._get_aspone_endpoint()
        decoded_xml = xml_content.decode('iso8859_15')
        response = self.env['account.report.async.document']._get_fr_webservice_answer(
            url=f"{endpoint}/api/l10n_fr_aspone/2/add_document",
            params={'db_uuid': db_uuid, 'xml_content': decoded_xml},
        )

        deposit_uid = ''
        if response.get('success'):
            deposit_uid = response['data'].get('deposit_id')

            if self.return_id:
                # If there are no errors when sending, we put the return state as submitted
                self.return_id.write({
                    'state': 'submitted',
                    'is_completed': True,
                })
                self.return_id._message_log(body=self.env._("The document %(document_name)s has been submitted to ASPOne.", document_name=export_name))

        if not deposit_uid:
            raise ValidationError(_("Error occurred while sending the report to the government : '%(response)s'", response=str(response)))

        document = self.env['account.report.async.document'].create({
            'name': export_name,
            'attachment_name': f'{export_name}.xml',
            'attachment': BinaryBytes(decoded_xml.encode()),
            'deposit_uid': deposit_uid,
            'state': 'sent',
        })

        self.report_async_document_ids = [Command.link(document.id)]

    def _check_duplicate_vat_declaration(self, date_from, date_to, recipient, xml_content):
        same_period_declarations = self.env['account.report.async.export'].search([
            ('date_from', '=', date_from),
            ('date_to', '=', date_to),
            ('recipient', '=', recipient),
        ])
        decoded_xml_content = xml_content.decode('iso8859_15').strip()
        for document in same_period_declarations.document_ids:
            decoded_attachment_content = document.attachment.decode().strip()
            if decoded_attachment_content == decoded_xml_content:
                return True

        return False
