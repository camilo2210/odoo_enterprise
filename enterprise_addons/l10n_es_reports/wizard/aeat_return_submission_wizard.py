import json
import re
from markupsafe import Markup

from odoo import models, fields, api, _
from odoo.tools import LazyTranslate
from odoo.exceptions import UserError, ValidationError
_lt = LazyTranslate(__name__)


AGENCIA_URL = 'https://sede.agenciatributaria.gob.es/'
LOGIN_PREFIX = _lt("Log in to the Spanish Tax Agency's portal:")
AGENCIA_LABEL = _lt("Agencia Tributaria")
IMPORT_INSTRUCTIONS = _lt("Choose the option to file by importing a file ('Importar') and upload the generated file when prompted.")
INSTRUCTIONS_BY_MODELO = {
    'l10n_es_reports.mod111.submission.wizard': {
        'navigate': _lt("Navigate to the appropriate section for tax returns and select 'Modelo 111'."),
        'review': _lt("Review the imported data and submit the declaration using your digital certificate or Cl@ve PIN."),
    },
    'l10n_es_reports.mod115.submission.wizard': {
        'navigate': _lt("Navigate to 'Impuestos y tasas' → 'Declaraciones' and select 'Modelo 115'."),
        'review': _lt("Review the imported data and submit with your digital certificate or Cl@ve PIN."),
    },
    'l10n_es_reports.mod130.submission.wizard': {
        'navigate': _lt("Navigate to 'Impuestos y tasas' → 'Declaraciones' and select 'Modelo 130'."),
        'review': _lt("Review the imported data, complete the payment details if applicable, and submit with your digital certificate or Cl@ve PIN."),
    },
    'l10n_es_reports.mod303.submission.wizard': {
        'navigate': _lt("Navigate to 'IVA' and select 'Modelo 303'."),
        'review': _lt("Review all the data, especially totals and bank details, then submit with your digital certificate or Cl@ve PIN."),
    },
    'l10n_es_reports.mod347.submission.wizard': {
        'navigate': _lt("Navigate to 'Declaraciones informativas' and select 'Modelo 347'."),
        'review': _lt("Review the imported data for accuracy and submit with your digital certificate or Cl@ve PIN."),
    },
    'l10n_es_reports.mod349.submission.wizard': {
        'navigate': _lt("Navigate to the section for tax returns and find the form 'Modelo 349'."),
        'review': _lt("Review and submit the declaration using your digital certificate or Cl@ve PIN."),
    },
    'l10n_es_reports.mod390.submission.wizard': {
        'navigate': _lt("Navigate to 'IVA' and select 'Modelo 390'."),
        'review': _lt("Carefully review all fields, ensuring the annual totals match your records, then submit with your digital certificate or Cl@ve PIN."),
    },
}


class L10nEsReportsModelosSubmissionWizard(models.TransientModel):
    _name = 'l10n_es_reports.modelos.submission.wizard'
    _inherit = 'account.return.submission.wizard'
    _description = 'Generic BOE Submission Wizard'

    submission_instructions = fields.Html(
        string="Submission Instructions",
        compute='_compute_submission_instructions',
    )

    def action_proceed_with_submission(self):
        self.ensure_one()
        if not self.env.company.vat:
            raise UserError(_("Please first set the TIN of your company."))
        options = self.return_id._get_closing_report_options()
        options['l10n_es_reports_boe_wizard_id'] = self.id
        modelo_number = self.return_id._l10n_es_get_report_modelo_number()
        self.return_id._add_attachment(self.env[f'l10n_es.mod{modelo_number}.tax.report.handler'].export_boe(options))
        return super().action_proceed_with_submission()

    def _compute_submission_instructions(self):
        for wizard in self:
            parts = []
            parts.append(Markup('<li>%s <a href="%s" target="_blank">%s</a>.</li>') % (str(LOGIN_PREFIX), str(AGENCIA_URL), str(AGENCIA_LABEL)))
            specific_instructions = INSTRUCTIONS_BY_MODELO.get(wizard._name, {})
            if specific_instructions:
                parts.append(Markup('<li>%s</li>') % str(specific_instructions.get('navigate')))
                parts.append(Markup('<li>%s</li>') % str(IMPORT_INSTRUCTIONS))
                parts.append(Markup('<li>%s</li>') % str(specific_instructions.get('review')))
                wizard.submission_instructions = ''.join(parts)

    def export_boe(self):
        options = self.return_id._get_closing_report_options()
        options['l10n_es_reports_boe_wizard_id'] = self.id

        modelo_number = self.return_id._l10n_es_get_report_modelo_number()
        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'model': self.env[f'l10n_es.mod{modelo_number}.tax.report.handler'],
                'options': json.dumps(options),
                'file_generator': 'export_boe',
                'no_closing_after_download': True,
            }
        }

    def print_xml(self):
        options = self.return_id._get_closing_report_options()
        submission_options = self._get_submission_options_to_inject()

        options.update(submission_options)

        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'model': self.env.context.get('model'),
                'options': json.dumps(options),
                'file_generator': 'export_tax_report_to_xml',
                'no_closing_after_download': True,
            }
        }


class L10n_Es_ReportsMod111_115_130_303ValidationWizard(models.TransientModel):
    _name = 'l10n_es_reports.mod111.115.130.303.submission.wizard'
    _inherit = 'l10n_es_reports.modelos.submission.wizard'
    _description = "BOE Submission Wizard for (mod111, mod115, mod130 & mod303)"

    def _get_current_company(self):
        return self.env.company

    company_id = fields.Many2one(string="Current Company", comodel_name='res.company', default=_get_current_company)
    company_partner_id = fields.Many2one(string="Company Partner", comodel_name='res.partner', related='company_id.partner_id')
    partner_bank_id = fields.Many2one(string="Direct Debit Account", comodel_name='res.partner.bank', help="The IBAN account number to use for direct debit. Leave blank if you don't use direct debit.", domain="[('partner_id','=',company_partner_id)]")
    complementary_declaration = fields.Boolean(string="Complementary Declaration", help="Whether or not this BOE file is a complementary declaration.")
    declaration_type = fields.Selection(string="Declaration Type", selection=[('I', 'I - Income'), ('U', 'U - Direct debit'), ('G', 'G - Income to enter on CCT'), ('N', 'N - To return')], required=True, default='I')
    previous_report_number = fields.Char(string="Previous Report Number", size=13, help="Number of the report previously submitted")

    @api.constrains('partner_bank_id')
    def validate_partner_bank_id(self):
        for record in self:
            if record.partner_bank_id and record.partner_bank_id.account_type != 'iban':
                raise ValidationError(_("Please select an IBAN account."))


class L10n_Es_ReportsMod111SubmissionWizard(models.TransientModel):
    _name = 'l10n_es_reports.mod111.submission.wizard'
    _inherit = 'l10n_es_reports.mod111.115.130.303.submission.wizard'
    _description = "BOE Submission Wizard for (mod111)"


class L10n_Es_ReportsMod115SubmissionWizard(models.TransientModel):
    _name = 'l10n_es_reports.mod115.submission.wizard'
    _inherit = 'l10n_es_reports.mod111.115.130.303.submission.wizard'
    _description = "BOE Submission Wizard for (mod115)"


class L10n_Es_ReportsMod130SubmissionWizard(models.TransientModel):
    _name = 'l10n_es_reports.mod130.submission.wizard'
    _inherit = 'l10n_es_reports.mod111.115.130.303.submission.wizard'
    _description = "BOE Submission Wizard for (mod130)"

    taxpayer_id = fields.Char(string="Taxpayer ID")
    taxpayer_first_name = fields.Char(string="Taxpayer first name")
    taxpayer_last_name = fields.Char(string="Taxpayer last name")


class L10n_Es_ReportsMod303SubmissionWizard(models.TransientModel):
    _name = 'l10n_es_reports.mod303.submission.wizard'
    _inherit = 'l10n_es_reports.mod111.115.130.303.submission.wizard'
    _description = "BOE Submission Wizard for (mod303)"

    monthly_return = fields.Boolean(string="In Monthly Return Register")
    declaration_type = fields.Selection(
        selection_add=[
            ('U', 'U - Direct Debit of the Income in CCC'),
            ('G', 'G - Tributaria Current Account - Income'),
            ('N', 'N - No Activity / Zero Result'),
            ('C', 'C - Compensation Request'),
            ('D', 'D - Return'),
            ('V', 'V - Tributaria Current Account - Return'),
            ('X', 'X - Return by Transfer Abroad (Only for Periods 3T, 4T and 07 to 12)'),
        ],
        ondelete={
            'C': 'cascade',
            'D': 'cascade',
            'V': 'cascade',
            'X': 'cascade',
        },
    )
    using_sii = fields.Boolean(string="Using SII Voluntarily", default=False)
    exempted_from_mod_390 = fields.Boolean(string="Exonerated From Modelo 390", default=False)
    exempted_from_mod_390_available = fields.Boolean(compute='_compute_show_exempted_from_mod_390', help="Technical field used to only make exempted_from_mod_390 avilable in the last period (12 or 4T)")

    # Rename according to the changes in Orden HAC/819/2024 (https://www.boe.es/eli/es/o/2024/07/30/hac819)
    complementary_declaration = fields.Boolean(
        string="Corrective Self-Assessment",
        help="Whether or not this BOE file is a corrective self-assessment."
    )

    rectification_direct_debit = fields.Boolean(string="As a result of the presentation of the corrective self-assessment, I request to cancel/modify the direct debit made")
    rectification_motive_rectifications = fields.Boolean(string="Rectifications (except those included in the following reason)")
    rectification_motive_discrepancy_adm_crit = fields.Boolean(string="Administrative criteria discrepancy")

    @api.depends('return_id')
    def _compute_show_exempted_from_mod_390(self):
        report = self.env.ref('l10n_es.mod_303')
        for record in self:
            options = record.return_id._get_closing_report_options()
            period = self.env[report.custom_handler_model_name]._get_mod_period_and_year(options)[0]
            record.exempted_from_mod_390_available = period in ('12', '4T')

    @api.constrains('partner_bank_id')
    def validate_bic(self):
        for record in self:
            if record.partner_bank_id and not record.partner_bank_id.bank_bic:
                raise ValidationError(_("Please first assign a BIC number to the bank related to this account."))

    def _get_using_sii_2021_value(self):
        return 1 if self.using_sii else 2

    def _get_exonerated_from_mod_390_2021_value(self, period):
        if period in ('12', '4T'):
            return 1 if self.exempted_from_mod_390 else 2
        return 0


class L10n_Es_ReportsMod347_349ValidationWizard(models.TransientModel):
    _name = 'l10n_es_reports.mod347.349.submission.wizard'
    _inherit = 'l10n_es_reports.modelos.submission.wizard'
    _description = "BOE Submission Wizard for (mod347 & mod349)"

    def _default_contact_name(self):
        return self.env.user.name

    def _default_contact_phone(self):
        return self.env.user.partner_id.phone

    contact_person_name = fields.Char(string="Contact person", default=_default_contact_name, required=True, help="Name of the contact person for this BOE file's submission")
    contact_person_phone = fields.Char(string="Contact phone number", default=_default_contact_phone, help="Phone number where to join the contact person")
    complementary_declaration = fields.Boolean(string="Complementary Declaration", help="Whether or not this BOE file corresponds to a complementary declaration")
    substitutive_declaration = fields.Boolean(string="Substitutive Declaration", help="Whether or not this BOE file corresponds to a substitutive declaration")
    previous_report_number = fields.Char(string="Previous Report Number", size=13, help="Number of the previous report, corrected or replaced by this one, if any")

    def get_formatted_contact_phone(self):
        return re.sub(r'\D', '', self.contact_person_phone or '')


class L10n_Es_ReportsMod347SubmissionWizard(models.TransientModel):
    _name = 'l10n_es_reports.mod347.submission.wizard'
    _inherit = 'l10n_es_reports.mod347.349.submission.wizard'
    _description = "BOE Submission Wizard for (mod347)"

    cash_basis_mod347_data = fields.One2many(
        comodel_name='l10n_es_reports.mod347.manual.partner.data',
        inverse_name='parent_wizard_id',
        string="Cash Basis Data",
        help="Manual entries containing the amounts perceived for the partners with cash basis criterion during this year. Leave empty for partners for which this criterion does not apply.")

    def l10n_es_get_partners_manual_parameters_map(self):
        cash_basis_dict = {}
        for data in self.cash_basis_mod347_data:
            if not cash_basis_dict.get(data.partner_id.id):
                cash_basis_dict[data.partner_id.id] = {'local_negocio': {'A': None, 'B': None}, 'seguros': {'B': None}, 'otras': {'A': None, 'B': None}}

            cash_basis_dict[data.partner_id.id][data.operation_class][data.operation_key] = data.perceived_amount

        return {'cash_basis': cash_basis_dict}


class L10n_Es_ReportsMod349SubmissionWizard(models.TransientModel):
    _name = 'l10n_es_reports.mod349.submission.wizard'
    _inherit = 'l10n_es_reports.mod347.349.submission.wizard'
    _description = "BOE Submission Wizard for (mod349)"

    trimester_2months_report = fields.Boolean(string="Trimester monthly report", help="Whether or not this BOE file must be generated with the data of the first two months of the trimester (in case its total amount of operation is above the threshold fixed by the law)")
    is_period_quarterly = fields.Boolean(compute='_compute_is_period_quarterly', help="Technical field to check if the return type periodicity is quaterly.")

    @api.depends('return_id')
    def _compute_is_period_quarterly(self):
        """
        Technical field to determine whether or not to display trimester_2months_report,
        which is only possible to select if the return periodicity is set to quaterly/trimester.
        """
        for wizard in self:
            period = self.return_id.type_id._get_periodicity(self.env.company)
            wizard.is_period_quarterly = period == 'trimester'


class L10n_Es_ReportsMod390SubmissionWizard(models.TransientModel):
    _name = 'l10n_es_reports.mod390.submission.wizard'
    _inherit = 'l10n_es_reports.modelos.submission.wizard'
    _description = "BOE Submission Wizard for (mod390)"

    physical_person_name = fields.Char(string="Natural Person - Name")
    monthly_return = fields.Boolean(string="Monthly return record in some period of the fiscal year")

    # The group number is not related to the NIF and must be completed if the company is in a group of entities.
    # See https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/manual-sociedades-2020/capitulo-2-identificac-carac-declarac-negocios/grupo-casillas-0009-00010-00081/entidades-dom-depend-grupo-fiscal-00010/numero-grupo-fiscal-casilla-00040.html
    is_in_tax_unit = fields.Boolean(string="Part of a tax unit", compute="_compute_is_in_tax_unit")
    group_number = fields.Char(string="Group of entities - Group Number")

    special_regime_applicable_163 = fields.Boolean(string="Special Regime Art. 163 is applicable")
    special_cash_basis = fields.Boolean(string="Special cash basis regime")
    special_cash_basis_beneficiary = fields.Boolean(string="Beneficiary of the special cash regime")

    is_substitute_declaration = fields.Boolean(string="Substitutive declaration?")
    is_substitute_decl_by_rectif_of_quotas = fields.Boolean(string="Substitutive declaration for correction of quotas")
    previous_decl_number = fields.Char(string="Previous declaration no.")

    principal_activity = fields.Char(string="Principal activity")
    principal_iae_epigrafe = fields.Char(string="Principal activity - Epígrafe")
    principal_code_activity = fields.Char(string="Principal activity - Activity Code")

    judicial_person_name = fields.Char(string="Representative - Name and Surname")
    judicial_person_nif = fields.Char(string="Representative - NIF")
    judicial_person_procuration_date = fields.Date(string="Representative - Power of Attorney Date")
    judicial_person_notary = fields.Char(string="Representative - Notary")

    def _compute_is_in_tax_unit(self):
        options = self.env.context.get('l10n_es_reports_report_options', {})
        tax_unit_opt = options.get('tax_unit')
        self.is_in_tax_unit = tax_unit_opt and tax_unit_opt != 'company_only'


class L10n_Es_ReportsAeatMod347ManualPartnerData(models.TransientModel):
    _name = 'l10n_es_reports.mod347.manual.partner.data'
    _description = "Manually Entered Data for Mod 347 Report"

    parent_wizard_id = fields.Many2one(comodel_name='l10n_es_reports.mod347.submission.wizard')
    partner_id = fields.Many2one(comodel_name='res.partner', string='Partner', required=True)
    perceived_amount = fields.Monetary(string='Perceived Amount', required=True)
    currency_id = fields.Many2one(comodel_name='res.currency', string='Currency', default=lambda self: self.env.company.currency_id)  # required by the monetary field
    operation_key = fields.Selection(selection=[('A', 'Adquisiciones de bienes y servicios'), ('B', 'Entregas de bienes y prestaciones de servicios')], required=True, string='Operation Key')
    operation_class = fields.Selection(selection=[('local_negocio', 'Arrendamiento Local Negocio'), ('seguros', 'Operaciones de Seguros'), ('otras', 'Otras operaciones')], required=True, string='Operation Class')
