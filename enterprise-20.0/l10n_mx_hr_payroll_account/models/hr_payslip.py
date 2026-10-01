# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from dateutil.relativedelta import relativedelta
from markupsafe import Markup
from werkzeug.urls import url_quote_plus
import logging

from odoo import api, fields, models
from odoo.addons.base.models.ir_qweb import keep_query
from odoo.addons.l10n_mx_edi.models.l10n_mx_edi_document import CFDI_DATE_FORMAT
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    l10n_mx_edi_document_ids = fields.One2many(
        comodel_name='l10n_mx_edi.document', inverse_name='payslip_id', copy=False, readonly=True)
    l10n_mx_edi_cfdi_state = fields.Selection(
        selection=[
            ('sent', 'Signed'),
            ('cancel', 'Cancelled'),
        ],
        string="CFDI status", store=True, copy=False, tracking=True,
        compute="_compute_l10n_mx_edi_cfdi_state_and_attachment")
    l10n_mx_edi_cfdi_sat_state = fields.Selection(
        selection=[
            ('valid', "Validated"),
            ('cancelled', "Cancelled"),
            ('not_found', "Not Found"),
            ('not_defined', "Not Defined"),
            ('error', "Error"),
        ],
        string="SAT status", store=True, copy=False, tracking=True,
        compute="_compute_l10n_mx_edi_cfdi_state_and_attachment")
    l10n_mx_edi_update_sat_needed = fields.Boolean(compute='_compute_l10n_mx_edi_update_sat_needed')
    l10n_mx_edi_cfdi_attachment_id = fields.Many2one(
        comodel_name='ir.attachment', string="CFDI", store=True, copy=False,
        compute='_compute_l10n_mx_edi_cfdi_state_and_attachment')

    l10n_mx_edi_cfdi_origin = fields.Char(
        string="CFDI Origin", copy=False, index='btree_not_null',
        help="In some cases like payments, credit notes, debit notes, invoices re-signed or invoices that are redone "
             "due to payment in advance will need this field filled, the format is:\n"
             "Origin Type|UUID1, UUID2, ...., UUIDn.\n"
             "Where the origin type could be:\n"
             "- 01: Nota de crédito\n"
             "- 02: Nota de débito de los documentos relacionados\n"
             "- 03: Devolución de mercancía sobre facturas o traslados previos\n"
             "- 04: Sustitución de los CFDI previos\n"
             "- 05: Traslados de mercancias facturados previamente\n"
             "- 06: Factura generada por los traslados previos\n"
             "- 07: CFDI por aplicación de anticipo")
    l10n_mx_edi_cfdi_uuid = fields.Char(
        string="Fiscal Folio", copy=False, store=True, tracking=True, index='btree_not_null',
        compute='_compute_l10n_mx_edi_cfdi_uuid',
        help="Folio in electronic invoice, is returned by SAT when send to stamp.")
    l10n_mx_edi_cfdi_cancel_id = fields.Many2one(
        comodel_name='hr.payslip', string="Substituted By", index='btree_not_null',
        compute='_compute_l10n_mx_edi_cfdi_cancel_id')

    # -------------------------------------------------------------------------
    # Compute Methods
    # -------------------------------------------------------------------------

    @api.depends('l10n_mx_edi_document_ids.state', 'l10n_mx_edi_document_ids.sat_state')
    def _compute_l10n_mx_edi_cfdi_state_and_attachment(self):
        for payslip in self:
            payslip.l10n_mx_edi_cfdi_sat_state = False
            payslip.l10n_mx_edi_cfdi_state = False
            payslip.l10n_mx_edi_cfdi_attachment_id = False

        for payslip in self.filtered(lambda p: p.country_code == 'MX'):
            for doc in payslip.l10n_mx_edi_document_ids.sorted():
                if doc.state == 'payslip_sent':
                    payslip.l10n_mx_edi_cfdi_sat_state = doc.sat_state
                    payslip.l10n_mx_edi_cfdi_state = 'sent'
                    payslip.l10n_mx_edi_cfdi_attachment_id = doc.attachment_id
                    break
                elif doc.state == 'payslip_cancel':
                    payslip.l10n_mx_edi_cfdi_sat_state = doc.sat_state
                    payslip.l10n_mx_edi_cfdi_state = 'cancel'
                    payslip.l10n_mx_edi_cfdi_attachment_id = doc.attachment_id
                    break

    @api.depends('l10n_mx_edi_cfdi_attachment_id')
    def _compute_l10n_mx_edi_cfdi_uuid(self):
        for payslip in self:
            payslip.l10n_mx_edi_cfdi_uuid = False

        for payslip in self.filtered(lambda p: p.country_code == 'MX'):
            if payslip.l10n_mx_edi_cfdi_attachment_id:
                cfdi_infos = self.env['l10n_mx_edi.document']._decode_cfdi_attachment(
                    payslip.l10n_mx_edi_cfdi_attachment_id.raw.content)
                payslip.l10n_mx_edi_cfdi_uuid = cfdi_infos.get('uuid')

    @api.depends('l10n_mx_edi_cfdi_uuid')
    def _compute_l10n_mx_edi_cfdi_cancel_id(self):
        for payslip in self:
            payslip.l10n_mx_edi_cfdi_cancel_id = False

        for payslip in self.filtered(lambda p: p.country_code == 'MX'):
            if payslip.company_id and payslip.l10n_mx_edi_cfdi_uuid:
                payslip.l10n_mx_edi_cfdi_cancel_id = payslip.search(
                    [
                        ('l10n_mx_edi_cfdi_origin', '=like', f'04|{payslip.l10n_mx_edi_cfdi_uuid}%'),
                        ('company_id', '=', payslip.company_id.id)
                    ], limit=1)

    @api.model
    def _issues_dependencies(self):
        return super()._issues_dependencies() + [
            'version_id.private_zip', 'employee_id.l10n_mx_rfc', 'company_id.l10n_mx_curp', 'company_id.l10n_mx_imss_id',
            'company_id.vat', 'move_id.state', 'version_id.employee_type_id.code', 'employee_id.registration_number',
            'employee_id.work_contact_id.state_id', 'company_id.partner_id.is_company', 'employee_id.l10n_mx_ssn',
            'employee_id.l10n_mx_curp', 'employee_id.bank_account_ids',
            'paid_date', 'l10n_mx_edi_cfdi_state',
        ]

    def _get_payslips_to_compute_issues(self):
        return super()._get_payslips_to_compute_issues() | self.filtered_domain([
            ('state', '=', 'paid'),
            ('country_code', '=', 'MX'),
            ('l10n_mx_edi_cfdi_state', '!=', 'sent'),
            ('date_to', '>', fields.Date.context_today(self) - relativedelta(months=3)),
        ])

    def _is_invalid(self):
        if self.country_code == 'MX':
            if not self.l10n_mx_edi_cfdi_uuid:
                return self.env._("This payslip is draft. This is not a legal document.")
            return False
        return super()._is_invalid()

    def _get_data_files_to_update(self):
        return super()._get_data_files_to_update() + [(
            'l10n_mx_hr_payroll_account', [
                'data/hr_salary_rule_data.xml',
            ])]

    def _get_accumulated_monthly_gross_wage(self):
        payslips_in_month = self._get_payslips_in_month() + self
        line_values = payslips_in_month._get_line_values(['GROSS'])

        accumulated_gross_wage = 0.0
        for slip in payslips_in_month:
            days_in_period = (slip.date_to - slip.date_from).days + 1
            days_in_current_month = min(days_in_period, slip.date_to.day)
            if self.date_from.month != slip.date_to.month:
                days_in_current_month = days_in_period - days_in_current_month
            accumulated_gross_wage += line_values['GROSS'][slip.id]['total'] / days_in_period * days_in_current_month

        return accumulated_gross_wage

    # -------------------------------------------------------------------------
    # CFDI Generation: Payslips
    # -------------------------------------------------------------------------

    def _l10n_mx_is_curp_needed(self):
        return (
            not self.company_id.partner_id.is_company
            or len(self.company_id.vat or "") == 13
        )

    def _l10n_mx_edi_add_payslip_cfdi_values(self, cfdi_values=None):
        self.ensure_one()
        if cfdi_values is None:
            if not self.l10n_mx_edi_cfdi_uuid:
                return defaultdict(str)
            cfdi_values = self.env['l10n_mx_edi.document']._get_company_cfdi_values(self.company_id)

        self.env['l10n_mx_edi.document']._add_base_cfdi_values(cfdi_values)
        self.env['l10n_mx_edi.document']._add_currency_cfdi_values(cfdi_values, self.currency_id)
        self.env['l10n_mx_edi.document']._add_document_origin_cfdi_values(cfdi_values, self.l10n_mx_edi_cfdi_origin)
        self.env['l10n_mx_edi.document']._add_customer_cfdi_values(cfdi_values, self.employee_id.user_partner_id)

        rules_amount = {line.salary_rule_id: abs(line.total) for line in self.line_ids}
        subsidy_rule = self.env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay_subsidy', raise_if_not_found=False)
        if subsidy_rule and subsidy_rule not in rules_amount:
            rules_amount[subsidy_rule] = 0

        mx_tz = self.employee_id._l10n_mx_edi_get_cfdi_timezone()
        cfdi_values['fecha'] = fields.Datetime.now().astimezone(mx_tz).strftime(CFDI_DATE_FORMAT)
        cfdi_values['tipo_de_comprobante'] = 'N'
        cfdi_values['serie'], _, cfdi_values['folio'] = self.move_id.name.rpartition('/')
        periodicity = self.version_id.l10n_mx_payment_periodicity if self.struct_id.l10n_mx_payroll_type == 'O' else '99'
        periodicity_label = dict(self.version_id._fields['l10n_mx_payment_periodicity']._description_selection(self.env)).get(periodicity)
        cfdi_values['periodo'] = f'{periodicity} - {periodicity_label}'

        cfdi_values['receptor'] = {
            'rfc': self.employee_id.l10n_mx_rfc,
            'nombre': self.env['l10n_mx_edi.document']._cfdi_sanitize_to_legal_name(self.employee_id.legal_name),
            'domicilio_fiscal_receptor': self.employee_id.private_zip,
        }

        cfdi_values['nomina'] = nomina = {
            'tipo_nomina': self.struct_id.l10n_mx_payroll_type,
            'fecha_pago': self.paid_date.isoformat(),
            'fecha_inicial_pago': self.date_from.isoformat(),
            'fecha_final_pago': self.date_to.isoformat(),
            'num_dias_pagados': self._get_schedule_days(),
        }

        cfdi_values['nomina_emisor'] = {
            'curp': self.company_id.l10n_mx_curp if self._l10n_mx_is_curp_needed() else False,
            'registro_patronal': self.company_id.l10n_mx_imss_id,
            'rfc_patron_origen': self.company_id.vat,
        }

        bank_account = self.employee_id.bank_account_ids[:1]
        is_clabe = bank_account and len(bank_account.sanitized_account_number) == 18
        base_contribution_salary_rule = self.env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay_base_contribution_salary', raise_if_not_found=False)
        base_contribution_salary = rules_amount[base_contribution_salary_rule] if base_contribution_salary_rule and base_contribution_salary_rule in rules_amount else 0
        cfdi_values['nomina_receptor'] = {
            'curp': self.employee_id.l10n_mx_curp,
            'num_seguridad_social': self.employee_id.l10n_mx_ssn,
            'fecha_inicio_rel_laboral': self.version_id.contract_date_start.isoformat(),
            'antigüedad': f'P{(self.date_to - self.version_id.contract_date_start).days // 7}W',
            'tipo_contrato': self.version_id.employee_type_id.code,
            'tipo_regimen': self.version_id.l10n_mx_regime_type,
            'tipo_jornada': self.version_id.l10n_mx_shift_type,
            'num_empleado': self.employee_id.registration_number,
            'riesgo_puesto': self.company_id.l10n_mx_risk_type,
            'periodicidad_pago': periodicity,
            'puesto': self.version_id.job_title,
            'departamento': self.version_id.department_id.name if self.version_id.department_id else False,
            'salario_base_cot_apor': base_contribution_salary,
            'salario_diario_integrado': self.l10n_mx_daily_salary,
            'clave_ent_fed': self.employee_id.work_contact_id.state_id.code,
            'cuenta_bancaria': bank_account.sanitized_account_number,
            'banco': bank_account._get_clearing_number('MX') if not is_clabe else None,
        }

        cfdi_values['percepcion_list'] = perceptions = []
        total_salaries = total_taxable = total_exempt = total_severance_pay = 0
        cfdi_values['deduccion_list'] = deductions = []
        total_taxes_withheld = total_other_deductions = 0
        cfdi_values['otro_pago_list'] = other_payments = []
        total_other_payments = 0

        rules = self.line_ids.salary_rule_id
        entitled_subsidy = round(next((line.amount for line in self.line_ids if line.code == 'SUBSIDY'), 0.0), 2)
        if 'SUBSIDY' not in rules.mapped('code'):
            rules |= subsidy_rule
        for rule in rules:
            concept = rule.l10n_mx_concept
            if not concept:
                continue

            amount = round(rules_amount.get(rule, 0), 2)
            if not amount and not (concept.cfdi_type == 'other' and concept.sat_code == '002'):
                continue

            # == PERCEPTIONS ==
            if concept.cfdi_type == 'perception':
                imp_gravado = amount if concept.is_taxable else 0
                imp_exento = amount if not concept.is_taxable else 0

                if imp_gravado == 0 and imp_exento == 0:
                    raise UserError(self.env._(
                        "Perception cannot have both Taxable (ImporteGravado) "
                        "and Exempt (ImporteExento) amounts set to 0 simultaneously."))

                if concept.sat_code == '038':
                    if imp_exento != 0:
                        raise UserError(self.env._(
                            "Perception '038' (Other Salary Income) cannot have a Tax-Exempt amount (ImporteExento). "
                            "It must be completely recorded under Taxable Income (ImporteGravado)."
                        ))
                    if imp_gravado <= 0:
                        raise UserError(self.env._(
                            "Perception '038' (Other Salary Income) must have a positive Taxable amount (ImporteGravado)."
                        ))

                perceptions.append({
                    'tipo_percepcion': concept.sat_code,
                    'clave': concept.payroll_code,
                    'concepto': concept.name,
                    'importe_gravado': imp_gravado,
                    'importe_exento': imp_exento,
                })

                if concept.is_taxable:
                    total_taxable += amount
                else:
                    total_exempt += amount
                if concept.sat_code not in ['022', '023', '025', '039', '044']:
                    total_salaries += amount
                if concept.sat_code in ['022', '023', '025']:
                    total_severance_pay += amount

            # == DEDUCTIONS ==
            elif concept.cfdi_type == 'deduction':
                deductions.append({
                    'tipo_deduccion': concept.sat_code,
                    'clave': concept.payroll_code,
                    'concepto': concept.name,
                    'importe': amount,
                })

                if concept.sat_code == '002':
                    total_taxes_withheld += amount
                else:
                    total_other_deductions += amount

            # == OTHER PAYMENTS ==
            else:
                other_payments.append({
                    'tipo_otro_pago': concept.sat_code,
                    'clave': concept.payroll_code,
                    'concepto': concept.name,
                    'importe': amount,
                    'subsidio_causado': entitled_subsidy if concept.sat_code == '002' else 0,
                    'saldo_a_favor': amount if concept.sat_code == '001' else 0,
                    'año': self.date_from.year,
                    'remanente_sal_fav': 0.0,
                })
                total_other_payments += amount

        # == SUB TOTALS ==
        total_perceptions = total_salaries + total_severance_pay
        nomina['total_percepciones'] = total_perceptions or None
        cfdi_values['nomina_percepciones'] = {
            'total_sueldos': total_salaries,
            'total_gravado': total_taxable,
            'total_exento': total_exempt,
        }

        total_deductions = total_taxes_withheld + total_other_deductions
        nomina['total_deducciones'] = total_deductions or None
        cfdi_values['nomina_deducciones'] = {
            'total_otras_deducciones': total_other_deductions,
            'total_impuestos_retenidos': total_taxes_withheld or None,
        }

        nomina['total_otros_pagos'] = total_other_payments

        # == INCAPACITIES AND UNPAID DAYS ==
        unpaid_days = 0
        cfdi_values['incapacidad_list'] = incapacities = []
        incapacities_days_by_code = defaultdict(int)
        for worked_days in self.worked_days_line_ids:
            if code := worked_days.work_entry_type_id.l10n_mx_sat_code:
                incapacities_days_by_code[code] += worked_days.number_of_days
            if not worked_days.is_paid:
                unpaid_days += worked_days.number_of_days

        for code, days in incapacities_days_by_code.items():
            incapacities.append({
                'tipo_incapacidad': code,
                'dias_incapacidad': days,
                'importe_monetario': days * self.l10n_mx_daily_salary,
            })

        cfdi_values['nomina']['num_dias_pagados'] -= unpaid_days

        num_dias_pagados = cfdi_values['nomina']['num_dias_pagados']
        for op in other_payments:
            if op['tipo_otro_pago'] == '002':
                subsidio_causado = op['subsidio_causado']
                if num_dias_pagados <= 31:
                    max_subsidy = 628.00
                else:
                    max_subsidy = num_dias_pagados * 0.206

                if subsidio_causado > max_subsidy:
                    raise UserError(self.env._(
                        "The Employment Subsidy (SubsidioCausado) exceeds the maximum allowed limit"
                    ))

        # == TOTALS ==
        cfdi_values['concepto'] = {
            'valor_unitario': total_perceptions + total_other_payments,
            'importe': total_perceptions + total_other_payments,
            'descuento': total_deductions,
        }

        cfdi_values['subtotal'] = round(total_perceptions + total_other_payments, 2)
        cfdi_values['descuento'] = round(total_deductions, 2)
        cfdi_values['total'] = round(cfdi_values['subtotal'] - cfdi_values['descuento'], 2)
        return cfdi_values

    # -------------------------------------------------------------------------
    # CFDI: DOCUMENTS
    # -------------------------------------------------------------------------

    def action_generate_cfdi(self):
        if self.filtered('error_count'):
            raise ValidationError(self._get_error_message())
        self._l10n_mx_edi_cfdi_try_send()
        if self.l10n_mx_edi_cfdi_uuid:
            self.action_print_cfdi()

    def action_print_cfdi(self):
        self._generate_pdf()

    def _l10n_mx_edi_get_cfdi_filename(self):
        return f"{self.move_id.name}-MX-Nómina-12.xml".replace('/', '-')

    def l10n_mx_edi_cfdi_try_sat(self):
        self.ensure_one()
        documents = self.l10n_mx_edi_document_ids
        for document in documents.filtered_domain(documents._get_update_sat_status_domain(from_cron=False)):
            document._update_sat_state()

    @api.depends('l10n_mx_edi_document_ids.state')
    def _compute_l10n_mx_edi_update_sat_needed(self):
        for payslip in self:
            payslip.l10n_mx_edi_update_sat_needed = bool(payslip.l10n_mx_edi_document_ids.filtered_domain(
                self.env['l10n_mx_edi.document']._get_update_sat_status_domain(from_cron=False)
            ))

    def _l10n_mx_edi_cfdi_payslip_update_sat_state(self, document, sat_state, error=None):
        """ Update the SAT state of the document for the current payslip.

        :param document:    The CFDI document to be updated.
        :param sat_state:   The newly fetched state from the SAT.
        :param error:       In case of error, the message returned by the SAT.
        """
        self.ensure_one()

        document.sat_state = sat_state
        document.message = None
        if sat_state == 'error' and error:
            document.message = error
            self.message_post(body=error)

    def _l10n_mx_edi_cfdi_try_send(self):
        """ Try to generate and send the CFDI for the current payslip. """
        self.ensure_one()
        if (self.state != 'paid' or not self.move_id or not self.move_id.name or
                self.l10n_mx_edi_cfdi_state not in (False, 'cancel')):
            return

        # == Check the config ==
        error = ""
        currency_precision = self.currency_id.l10n_mx_edi_decimal_places
        if not currency_precision:
            error = self.env._(
                "The SAT does not provide information for the currency %s.\n"
                "You must get manually a key from the PAC to confirm the "
                "currency rate is accurate enough.",
                self.currency_id)
        if error:
            self._l10n_mx_edi_cfdi_sent_failed(error)
            return

        # == Lock ==
        self.env['res.company']._with_locked_records(self)

        # == Send ==
        def on_populate(cfdi_values):
            self._l10n_mx_edi_add_payslip_cfdi_values(cfdi_values)

        def on_failure(error, cfdi_filename=None, cfdi_str=None):
            document = self._l10n_mx_edi_cfdi_sent_failed(error, cfdi_filename=cfdi_filename, cfdi_str=cfdi_str)
            _logger.error('An error occurred while signing the CFDI document with the government.\n%s\n', error)
            self.message_post(
                body=self.env._(
                    "An error occurred while signing the CFDI document with the government:%(error)s",
                    error=Markup("<br/><b>%s</b>") % error),
                attachment_ids=document.attachment_id.ids)

        def on_success(_cfdi_values, cfdi_filename, cfdi_str, populate_return=None):
            document = self._l10n_mx_edi_cfdi_sent(cfdi_filename, cfdi_str)
            self.message_post(
                body=self.env._("The CFDI document was successfully created and signed by the government."),
                attachment_ids=document.attachment_id.ids)
            self.move_id.l10n_mx_edi_cfdi_uuid = self.l10n_mx_edi_cfdi_uuid

        self.env['l10n_mx_edi.document']._send_api(
            self.company_id,
            'l10n_mx_hr_payroll_account.cfdiv40_nomina',
            self._l10n_mx_edi_get_cfdi_filename(),
            on_populate,
            on_failure,
            on_success,
        )

    def _l10n_mx_edi_cfdi_sent(self, cfdi_filename, cfdi_str):
        """ Create/update the payslip document for 'sent'.

        :param cfdi_filename:   The filename of the cfdi.
        :param cfdi_str:        The content of the cfdi.
        """
        self.ensure_one()

        document_values = {
            'company_id': self.company_id.id,
            'payslip_id': self.id,
            'state': 'payslip_sent',
            'sat_state': 'not_defined',
            'message': None,
            'attachment_id': {
                'name': cfdi_filename,
                'raw': cfdi_str,
                'res_model': self._name,
                'res_id': self.id,
                'description': "CFDI",
            },
        }
        return self.env['l10n_mx_edi.document']._create_update_payslip_document(self, document_values)

    def _l10n_mx_edi_cfdi_sent_failed(self, error, cfdi_filename=None, cfdi_str=None):
        """ Create/update the payslip document for 'sent_failed'.

        :param error:           The error.
        :param cfdi_filename:   The optional filename of the cfdi.
        :param cfdi_str:        The optional content of the cfdi.
        :return:                The created/updated document.
        """
        self.ensure_one()

        document_values = {
            'company_id': self.company_id.id,
            'payslip_id': self.id,
            'state': 'payslip_sent_failed',
            'sat_state': None,
            'message': error,
        }
        if cfdi_filename and cfdi_str:
            document_values['attachment_id'] = {
                'name': cfdi_filename,
                'raw': cfdi_str,
            }
        return self.env['l10n_mx_edi.document']._create_update_payslip_document(self, document_values)

    def _l10n_mx_edi_get_extra_report_values(self):
        cfdi_infos = self.env['l10n_mx_edi.document']._decode_cfdi_attachment(
            self.l10n_mx_edi_cfdi_attachment_id.raw.content)
        if not cfdi_infos:
            return {}

        barcode_value_params = keep_query(
            id=cfdi_infos['uuid'],
            re=cfdi_infos['supplier_rfc'],
            rr=cfdi_infos['customer_rfc'],
            tt=cfdi_infos['amount_total'],
        )
        barcode_sello = url_quote_plus(cfdi_infos['sello'][-8:], safe='=/').replace('%2B', '+')
        barcode_value = url_quote_plus(f'https://verificacfdi.facturaelectronica.sat.gob.mx/default.aspx?{barcode_value_params}&fe={barcode_sello}')
        barcode_src = f'/report/barcode/?barcode_type=QR&value={barcode_value}&width=180&height=180'

        return {
            **cfdi_infos,
            'barcode_src': barcode_src,
        }

    def _check_send_payslip_mail(self):
        self.ensure_one()
        if self.country_code == 'MX' and not self.l10n_mx_edi_cfdi_uuid:
            return False
        return super()._check_send_payslip_mail()

    def _issue_mx_employee_fields(self):
        issues = []
        # Version Fields
        if not self.version_id.private_zip:
            issues.append({
                'message': self.env._('Private ZIP required on the employee'),
                'action_text': self.env._("Employee"),
                'action': self.employee_id._get_records_action(
                    name=self.env._("Employee"),
                    target='new',
                    context={**self.env.context, 'version_id': self.version_id.id},
                ),
                'level': 'danger' if self.state == 'paid' else 'warning',
            })
        if not self.version_id.employee_type_id:
            issues.append({
                'message': self.env._('Contract Type required on the employee'),
                'action_text': self.env._("Employee"),
                'action': self.employee_id._get_records_action(
                    name=self.env._("Employee"),
                    target='new',
                    context={**self.env.context, 'version_id': self.version_id.id},
                ),
                'level': 'danger' if self.state == 'paid' else 'warning',
            })
        elif self.version_id.employee_type_id.code not in ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '99']:
            issues.append({
                'message': self.env._('Invalid Contract Type code on the employee'),
                'action_text': self.env._("Employee"),
                'action': self.employee_id._get_records_action(
                    name=self.env._("Employee"),
                    target='new',
                    context={**self.env.context, 'version_id': self.version_id.id},
                ),
                'level': 'danger' if self.state == 'paid' else 'warning',
            })

        # Employee Fields
        if not self.employee_id.registration_number:
            issues.append({
                'message': self.env._('Employee Reference required on the employee'),
                'action_text': self.env._("Employee"),
                'action': self.employee_id._get_records_action(
                    name=self.env._("Employee"),
                    target='new',
                    context={**self.env.context, 'version_id': self.version_id.id},
                ),
                'level': 'danger' if self.state == 'paid' else 'warning',
            })
        if not self.employee_id.l10n_mx_rfc:
            issues.append({
                'message': self.env._('RFC required on the employee'),
                'action_text': self.env._("Employee"),
                'action': self.employee_id._get_records_action(
                    name=self.env._("Employee"),
                    target='new',
                    context={**self.env.context, 'version_id': self.version_id.id},
                ),
                'level': 'danger' if self.state == 'paid' else 'warning',
            })
        if not self.employee_id.l10n_mx_curp:
            issues.append({
                'message': self.env._('CURP required on the employee'),
                'action_text': self.env._("Employee"),
                'action': self.employee_id._get_records_action(
                    name=self.env._("Employee"),
                    target='new',
                    context={**self.env.context, 'version_id': self.version_id.id},
                ),
                'level': 'danger' if self.state == 'paid' else 'warning',
            })
        if not self.employee_id.work_contact_id:
            issues.append({
                'message': self.env._('Work Contact required on the employee'),
                'action_text': self.env._("Employee"),
                'action': self.employee_id._get_records_action(
                    name=self.env._("Employee"),
                    target='new',
                    context={**self.env.context, 'version_id': self.version_id.id},
                ),
                'level': 'danger' if self.state == 'paid' else 'warning',
            })
        elif not self.employee_id.work_contact_id.state_id:
            issues.append({
                'message': self.env._('State required on the work contact'),
                'action_text': self.env._("Work Contact"),
                'action': self.employee_id.work_contact_id._get_records_action(
                    name=self.env._("Work Contact"),
                    target='new',
                ),
                'level': 'danger' if self.state == 'paid' else 'warning',
            })
        if not self.employee_id.bank_account_ids:
            issues.append({
                'message': self.env._('Bank Account required on the employee'),
                'action_text': self.env._("Employee"),
                'action': self.employee_id._get_records_action(
                    name=self.env._("Employee"),
                    target='new',
                    context={**self.env.context, 'version_id': self.version_id.id},
                ),
                'level': 'danger' if self.state == 'paid' else 'warning',
            })

        return issues or None

    def _issue_mx_warnings(self):
        issues = []
        # Company Fields
        if not self.company_id.l10n_mx_curp and self._l10n_mx_is_curp_needed():
            issues.append({
                'message': self.env._('CURP missing on the company'),
                'action_text': self.env._("Settings"),
                'action': self.env['ir.actions.actions']._for_xml_id('hr_payroll.action_hr_payroll_configuration'),
                'level': 'warning',
            })
        if not self.company_id.l10n_mx_imss_id:
            issues.append({
                'message': self.env._('IMSS ID missing on the company'),
                'action_text': self.env._("Settings"),
                'action': self.env['ir.actions.actions']._for_xml_id('hr_payroll.action_hr_payroll_configuration'),
                'level': 'warning',
            })
        if not self.company_id.vat:
            issues.append({
                'message': self.env._('VAT missing on the company'),
                'action_text': self.env._("Settings"),
                'action': self.env['ir.actions.actions']._for_xml_id('account.action_account_config'),
                'level': 'warning',
            })

        # Employee Fields
        if not self.employee_id.l10n_mx_ssn:
            issues.append({
                'message': self.env._('SSN ID missing on the employee'),
                'action_text': self.env._("Employee"),
                'action': self.employee_id._get_records_action(
                    name=self.env._("Employee"),
                    target='new',
                    context={**self.env.context, 'version_id': self.version_id.id},
                ),
                'level': 'warning',
            })

        # -- Adjustments salary --
        if (
            self.date_from + relativedelta(day=31) <= self.date_to
            and self._get_accumulated_monthly_subsidy()
            and self._get_accumulated_monthly_gross_wage() > self._rule_parameter('l10n_mx_subsidy_salary_limit', self.date_from)
        ):
            issues.append({
                'message': self.env._('This employee exceeds the "Salary Limit for Employment Subsidy" - Validate Subsidy and ISR Adjustments'),
                'action_text': self.env._("Payslip(s)"),
                'action': self._get_payslips_in_month()._get_records_action(),
                'level': 'warning',
            })

        if self.l10n_mx_is_integration_factor_manual:
            issues.append({
                'message': self.env._('The integration factor value has been manually modified. Please verify this change before continuing.'),
                'action_text': self.env._('Reset & Compute Sheet'),
                'action': {
                    'type': 'object',
                    'name': 'action_reset_integration_factor',
                },
                'level': 'warning',
            })

        return issues or None
