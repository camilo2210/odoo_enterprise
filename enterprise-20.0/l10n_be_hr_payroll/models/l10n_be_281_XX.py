# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from lxml import etree

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import BinaryBytes, file_path

from stdnum.be.vat import compact as vat_be_compact

_logger = logging.getLogger(__name__)

# Sources:
# - Technical Doc https://finances.belgium.be/fr/E-services/Belcotaxonweb/documentation-technique
# - "Avis aux débiteurs" https://finances.belgium.be/fr/entreprises/personnel_et_remuneration/avis_aux_debiteurs#q2

COUNTRY_CODES = {
    'AD': '00102', 'AE': '00260', 'AF': '00251', 'AG': '00403', 'AI': '00490', 'AL': '00101', 'AM': '00249',
    'AO': '00341', 'AR': '00511', 'AS': '00690', 'AT': '00105', 'AU': '00611', 'AZ': '00250', 'BA': '00149',
    'BB': '00423', 'BD': '00237', 'BE': '00000', 'BF': '00308', 'BG': '00106', 'BH': '00268', 'BI': '00303',
    'BJ': '00310', 'BM': '00485', 'BN': '00224', 'BO': '00512', 'BR': '00513', 'BS': '00425', 'BT': '00223',
    'BW': '00302', 'BY': '00142', 'BZ': '00430', 'CA': '00401', 'CD': '00306', 'CF': '00305', 'CG': '00307',
    'CH': '00127', 'CI': '00309', 'CK': '00687', 'CL': '00514', 'CM': '00304', 'CN': '00218', 'CO': '00515',
    'CR': '00411', 'CU': '00412', 'CV': '00339', 'CY': '00107', 'CZ': '00140', 'DE': '00103', 'DJ': '00345',
    'DK': '00108', 'DM': '00480', 'DO': '00427', 'DZ': '00351', 'EC': '00516', 'EE': '00136', 'EG': '00352',
    'EH': '00388', 'ER': '00349', 'ES': '00109', 'ET': '00311', 'FI': '00110', 'FJ': '00617', 'FK': '00580',
    'FM': '00602', 'FR': '00111', 'GA': '00312', 'GB': '00112', 'GD': '00426', 'GE': '00253', 'GF': '00581',
    'GH': '00314', 'GI': '00180', 'GL': '00498', 'GM': '00313', 'GN': '00315', 'GP': '00496', 'GQ': '00337',
    'GR': '00114', 'GT': '00413', 'GU': '00681', 'GW': '00338', 'GY': '00521', 'HK': '00234', 'HN': '00414',
    'HR': '00146', 'HT': '00419', 'HU': '00115', 'ID': '00208', 'IE': '00116', 'IL': '00256', 'IN': '00207',
    'IQ': '00254', 'IR': '00255', 'IS': '00117', 'IT': '00128', 'JM': '00415', 'JO': '00257', 'JP': '00209',
    'KE': '00336', 'KG': '00226', 'KH': '00216', 'KI': '00622', 'KM': '00343', 'KN': '00431', 'KP': '00219',
    'KR': '00206', 'KW': '00264', 'KY': '00492', 'KZ': '00225', 'LA': '00210', 'LB': '00258', 'LC': '00428',
    'LI': '00118', 'LK': '00203', 'LR': '00318', 'LS': '00301', 'LT': '00137', 'LU': '00113', 'LV': '00135',
    'LY': '00353', 'MA': '00354', 'MC': '00120', 'MD': '00144', 'ME': '00151', 'MG': '00324', 'MH': '00603',
    'MK': '00148', 'ML': '00319', 'MM': '00201', 'MN': '00221', 'MO': '00281', 'MQ': '00497', 'MR': '00355',
    'MS': '00493', 'MT': '00119', 'MU': '00317', 'MV': '00222', 'MW': '00358', 'MX': '00416', 'MY': '00212',
    'MZ': '00340', 'NA': '00384', 'NC': '00683', 'NE': '00321', 'NG': '00322', 'NI': '00417', 'NL': '00129',
    'NO': '00121', 'NP': '00213', 'NR': '00615', 'NU': '00604', 'NZ': '00613', 'OM': '00266', 'PA': '00418',
    'PE': '00518', 'PF': '00684', 'PG': '00619', 'PH': '00214', 'PK': '00259', 'PL': '00122', 'PM': '00495',
    'PN': '00692', 'PR': '00487', 'PS': '00271', 'PT': '00123', 'PW': '00679', 'PY': '00517', 'QA': '00267',
    'RE': '00387', 'RO': '00124', 'RS': '00152', 'RU': '00145', 'RW': '00327', 'SA': '00252', 'SB': '00623',
    'SC': '00342', 'SD': '00356', 'SE': '00126', 'SG': '00205', 'SH': '00389', 'SI': '00147', 'SK': '00141',
    'SL': '00328', 'SM': '00125', 'SN': '00320', 'SO': '00329', 'SR': '00522', 'SS': '00365', 'SV': '00421',
    'SY': '00261', 'SZ': '00347', 'TC': '00488', 'TD': '00333', 'TG': '00334', 'TH': '00235', 'TJ': '00228',
    'TL': '00282', 'TM': '00229', 'TN': '00357', 'TO': '00616', 'TR': '00262', 'TT': '00422', 'TV': '00621',
    'TW': '00204', 'TZ': '00332', 'UA': '00143', 'UG': '00323', 'US': '00402', 'UY': '00519', 'UZ': '00227',
    'VA': '00133', 'VC': '00429', 'VE': '00520', 'VG': '00479', 'VI': '00478', 'VN': '00220', 'VU': '00624',
    'WF': '00689', 'WS': '00614', 'XK': '00153', 'YE': '00270', 'ZA': '00325', 'ZM': '00335', 'ZW': '00344'
}
REPORT_CONFIG = {
    '281.10': {
        'model': 'l10n_be.281_10',
        'relation_field': 'l10n_be_281_10_ids',
        'include_field': 'include_281_10',
        'count_field': 'l10n_be_281_10_id_lines_count',
    },
    '281.13': {
        'model': 'l10n_be.281_13',
        'relation_field': 'l10n_be_281_13_ids',
        'include_field': 'include_281_13',
        'count_field': 'l10n_be_281_13_id_lines_count',
    },
    '281.18': {
        'model': 'l10n_be.281_18',
        'relation_field': 'l10n_be_281_18_ids',
        'include_field': 'include_281_18',
        'count_field': 'l10n_be_281_18_id_lines_count',
    },
    '281.20': {
        'model': 'l10n_be.281_20',
        'relation_field': 'l10n_be_281_20_ids',
        'include_field': 'include_281_20',
        'count_field': 'l10n_be_281_20_id_lines_count',
    },
    '281.30': {
        'model': 'l10n_be.281_30',
        'relation_field': 'l10n_be_281_30_ids',
        'include_field': 'include_281_30',
        'count_field': 'l10n_be_281_30_id_lines_count',
    },
    '281.45': {
        'model': 'l10n_be.281_45',
        'relation_field': 'l10n_be_281_45_ids',
        'include_field': 'include_281_45',
        'count_field': 'l10n_be_281_45_id_lines_count',
    },
}


class L10n_Be281_XX(models.Model):
    _name = 'l10n_be.281_xx'
    _description = 'HR Payroll 281.XX Declaration'
    _order = 'year'

    active = fields.Boolean(default=True)
    reference = fields.Char(string="Reference", copy=False)
    name = fields.Char(string="Name", required=True, copy=False, readonly=True, default="Draft")
    year = fields.Selection(
        selection='_get_year_selection', string='Year', required=True,
        default=lambda x: str(fields.Date.today().year - 1))
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('error', 'Error'),
        ('ready', 'Ready'),
        ('done', 'Done'),
        ('cancel', 'Cancel')
    ], default='draft', readonly=True)
    type_sending = fields.Selection([
        ('0', 'Original'),
        ('1', 'Corrections'),
    ], string="Sending Type", default='0', required=True)
    type_treatment = fields.Selection([
        ('0', 'Original'),
        ('1', 'Modification'),
        ('2', 'Add'),
        ('3', 'Cancel'),
    ], string="Treatment Type", default='0', required=True)
    untaxed_employee_ids = fields.Many2many('hr.employee', readonly=True)

    form_types_display = fields.Char(string="Form types", compute="_compute_form_types_display")

    is_correction_needed = fields.Boolean('Correction Needed', copy=False)
    origin_id = fields.Many2one('l10n_be.281_xx', string="Original", ondelete='cascade', index='btree_not_null')
    correction_ids = fields.One2many('l10n_be.281_xx', 'origin_id', string="Corrections")

    payslip_ids = fields.Many2many('hr.payslip', 'l10n_be_281_xx_hr_payslip_rel', 'l10n_be_281_xx_id', 'payslip_id')

    # 281.10 report fields
    l10n_be_281_10_ids = fields.One2many('l10n_be.281_10', 'declaration_id', copy=False)
    include_281_10 = fields.Boolean(string="Include 281.10", default=True)
    l10n_be_281_10_line_ids = fields.One2many(related='l10n_be_281_10_ids.line_ids', string="281.10 Declarations")
    l10n_be_281_10_id_lines_count = fields.Integer(related="l10n_be_281_10_ids.lines_count", string="Eligible Employees 281.10")

    # 281.13 report fields
    l10n_be_281_13_ids = fields.One2many('l10n_be.281_13', 'declaration_id')
    include_281_13 = fields.Boolean(string="Include 281.13", default=True)
    l10n_be_281_13_line_ids = fields.One2many(related='l10n_be_281_13_ids.line_ids', string="281.13 Declarations")
    l10n_be_281_13_id_lines_count = fields.Integer(related="l10n_be_281_13_ids.lines_count", string="Eligible Employees 281.13")

    # 281.18 report fields
    l10n_be_281_18_ids = fields.One2many('l10n_be.281_18', 'declaration_id', copy=False)
    include_281_18 = fields.Boolean(string="Include 281.18", default=True)
    l10n_be_281_18_line_ids = fields.One2many(related='l10n_be_281_18_ids.line_ids', string="281.18 Declarations")
    l10n_be_281_18_id_lines_count = fields.Integer(related="l10n_be_281_18_ids.lines_count", string="Eligible Employees 281.18")

    # 281.20 report fields
    l10n_be_281_20_ids = fields.One2many('l10n_be.281_20', 'declaration_id', copy=False)
    include_281_20 = fields.Boolean(string="Include 281.20", default=True)
    l10n_be_281_20_line_ids = fields.One2many(related='l10n_be_281_20_ids.line_ids', string="281.20 Declarations")
    l10n_be_281_20_id_lines_count = fields.Integer(related="l10n_be_281_20_ids.lines_count", string="Eligible Employees 281.20")

    # 281.30 report fields
    l10n_be_281_30_ids = fields.One2many('l10n_be.281_30', 'declaration_id')
    include_281_30 = fields.Boolean(string="Include 281.30", default=True)
    l10n_be_281_30_line_ids = fields.One2many(related='l10n_be_281_30_ids.line_ids', string="281.30 Declarations")
    l10n_be_281_30_id_lines_count = fields.Integer(related="l10n_be_281_30_ids.lines_count", string="Eligible Employees 281.30")

    # 281.45 report fields
    l10n_be_281_45_ids = fields.One2many('l10n_be.281_45', 'declaration_id', copy=False)
    include_281_45 = fields.Boolean(string="Include 281.45", default=True)
    l10n_be_281_45_line_ids = fields.One2many(related='l10n_be_281_45_ids.line_ids', string="281.45 Declarations")
    l10n_be_281_45_id_lines_count = fields.Integer(related="l10n_be_281_45_ids.lines_count", string="Eligible Employees 281.45")

    test_xml_file = fields.Binary('Test XML', readonly=True, attachment=False, copy=False)
    test_xml_filename = fields.Char(copy=False)
    xml_file = fields.Binary('XML File', readonly=True, attachment=False, copy=False)
    xml_filename = fields.Char(copy=False)

    error_message = fields.Text('Error Message', readonly=True, copy=False)

    @api.model
    def default_get(self, fields):
        if self.env.company.country_id.code != 'BE':
            raise UserError(self.env._('You must be logged in a BE company to use this feature'))
        return super().default_get(fields)

    @api.model
    def _get_year_selection(self):
        current_year = fields.Date.today().year
        return [(str(i), i) for i in range(1990, current_year + 1)]

    @api.model
    def _get_lang_code(self, lang):
        lang_dict = {
            'nl_NL': 1,
            'fr_FR': 2,
            'de_DE': 3,
        }
        return lang_dict.get(lang, 0)

    @api.model
    def _get_country_code(self, country):
        return COUNTRY_CODES[country.code]

    @api.model_create_multi
    def create(self, vals_list):
        target_years = list({vals.get('year') for vals in vals_list})
        year_counts = dict(self._read_group(domain=[('year', 'in', target_years)], groupby=['year'], aggregates=['__count']))
        for vals in vals_list:
            year = vals.get('year')
            year_counts[year] = year_counts.get(year, 0) + 1
            vals['name'] = f"{year}_281_{year_counts[year]}"
        reports = super().create(vals_list)
        related_vals = [{'declaration_id': report.id} for report in reports]
        for config in REPORT_CONFIG.values():
            self.env[config['model']].create(related_vals)
        return reports

    @api.depends('include_281_10', 'l10n_be_281_10_id_lines_count', 'include_281_13', 'l10n_be_281_13_id_lines_count',
        'include_281_18', 'l10n_be_281_18_id_lines_count', 'include_281_20', 'l10n_be_281_20_id_lines_count',
        'include_281_30', 'l10n_be_281_30_id_lines_count', 'include_281_45', 'l10n_be_281_45_id_lines_count')
    def _compute_form_types_display(self):
        for record in self:
            types = []
            for report_key, config in REPORT_CONFIG.items():
                if record[config['include_field']] and record[config['count_field']]:
                    types.append(report_key)
            record.form_types_display = ', '.join(types)

    def _validate_xml_content(self, file_content, success_state):
        self.ensure_one()
        xsd_schema_file_path = file_path('l10n_be_hr_payroll/data/Belcotax-2025.xsd')
        xsd_root = etree.parse(xsd_schema_file_path)
        schema = etree.XMLSchema(xsd_root)
        xml_root = etree.fromstring(file_content)
        try:
            schema.assertValid(xml_root)
            self.error_message = False
            self.state = success_state
        except etree.DocumentInvalid as err:
            self.error_message = str(err)
            self.state = 'error'

    def _check_company_configuration(self):
        if not self.company_id.vat or not self.company_id.zip:
            raise UserError(self.env._('The VAT or the ZIP number is not specified on your company'))
        if not self.company_id.phone:
            raise UserError(self.env._("The phone number is not specified on your company."))
        try:
            self.company_id._phone_format(
                number=self.company_id.phone,
                raise_exception=True,
            )
        except UserError as e:
            raise UserError(self.env._("The phone number is invalid.")) from e

    def _get_main_data(self):
        self.ensure_one()
        self._check_company_configuration()
        bce_number = vat_be_compact(self.company_id.vat)
        is_test = self.env.context.get('is_test', False)
        return {
            'v0002_inkomstenjaar': self.year,
            'v0010_bestandtype': 'BELCOTST' if is_test else 'BELCOTAX',
            'v0011_aanmaakdatum': fields.Date.today().strftime('%d-%m-%Y'),
            'v0014_naam': self.company_id.name,
            'v0015_adres': self.company_id.street,
            'v0016_postcode': self.company_id.zip,
            'v0017_gemeente': self.company_id.city,
            'v0018_telefoonnummer': self.company_id._phone_format(number=self.company_id.phone),
            'v0021_contactpersoon': self.env.user.name,
            'v0022_taalcode': self._get_lang_code(self.env.user.lang),
            'v0023_emailadres': self.env.user.email,
            'v0024_nationaalnr': bce_number,
            'v0025_typeenvoi': self.type_sending,
            'a1002_inkomstenjaar': self.year,
            'a1005_registratienummer': bce_number,
            'a1011_naamnl1': self.company_id.name,
            'a1013_adresnl': self.company_id.street,
            'a1014_postcodebelgisch': self.company_id.zip.strip(),
            'a1015_gemeente': self.company_id.city,
            'a1016_landwoonplaats': self._get_country_code(self.company_id.country_id),
            'a1020_taalcode': 1,
        }

    def _get_xml_rendering_data(self):
        self.ensure_one()
        main_data = self._get_main_data()

        sequence = 0
        total_volgnummer = 0
        total_control = 0
        total_withholding = 0
        sheets_count = 0
        declarations_count = 0
        employees_data_map = {}
        employee_errors = []
        for report_key, config in REPORT_CONFIG.items():
            result = {'employees_data': [], 'sum_volgnummer': 0, 'sum_control_total': 0, 'sum_withholding': 0, 'employees_with_error': {}}
            if self[config['include_field']] and self[config['count_field']]:
                report = self[config['relation_field']]
                employees = report.line_ids.employee_id
                context_args = {'starting_sequence': sequence, 'round_281': True}
                result = report.with_context(**context_args)._get_rendering_data(employees)
                mapping_lines = result['mapping_lines']
                for employee_data in result['employees_data']:
                    employee_data['_xml_declaration_fields'] = report._get_xml_declaration_fields_markup(
                        employee_data, mapping_lines,
                    )
                declarations_count += 1
            if result.get('employees_with_error'):
                for error_msg in result['employees_with_error'].values():
                    employee_errors.append(f"- {error_msg}")
            report_number = report_key.split('.')[1]
            employees_data_map[f'employees_data_{report_number}'] = result['employees_data']
            sequence += len(result['employees_data'])
            sheets_count += len(result['employees_data'])
            total_volgnummer += result['sum_volgnummer']
            total_control += result['sum_control_total']
            total_withholding += result['sum_withholding']

        if employee_errors:
            error_header = self.env._("Cannot generate the XML file. Please fix the following employee errors:\n\n")
            return {'employee_error': error_header + "\n".join(employee_errors)}

        total_data = {
            'r8002_inkomstenjaar': self.year,
            'r8005_registratienummer': main_data['a1005_registratienummer'],
            # Le champ "Nombre total d'enregistrements" (8010) doit être égal au nombre
            # d'enregistrements  contenus dans cette déclaration (total des enregistrements
            # de type 2 (fiches) + enregistrement 1 et 8)
            'r8010_aantalrecords': sheets_count + 2,
            'r8011_controletotaal': total_volgnummer,
            'r8012_controletotaal': total_control,
            'r8013_totaalvoorheffingen': total_withholding,
            'r9002_inkomstenjaar': self.year,
            # Le champ "Nombre de déclarations" doit être égal au nombre de déclarations
            # contenues dans l'envoi + 2.
            'r9010_aantallogbestanden': declarations_count + 2,
            # Le champ "Nombre de fiches" doit être égal au nombre d'enregistrements contenus
            # dans cet envoi  (total des enregistrements de type 2 (fiches) + total des
            # enregistrements 1 et 8 (début et fin débiteurs) + enregistrements 0 et 9 (début et fin d'envoi)).
            'r9011_totaalaantalrecords': sheets_count + 4,
            'r9012_controletotaal': total_volgnummer,
            'r9013_controletotaal': total_control,
            'r9014_controletotaal': total_withholding,
        }

        result = {
            'data': main_data,
            'total_data': total_data,
        }
        result.update(employees_data_map)
        return result

    def _render_xml(self, is_test=False):
        self.ensure_one()
        rendering_data = self.with_context(is_test=is_test)._get_xml_rendering_data()
        if rendering_data.get('employee_error'):
            return False, rendering_data['employee_error']
        xml_str = self.env['ir.qweb']._render('l10n_be_hr_payroll.281_xx_xml_report', rendering_data)
        root = etree.fromstring(xml_str, parser=etree.XMLParser(remove_blank_text=True, resolve_entities=False))
        xml_formatted_str = etree.tostring(root, pretty_print=True, encoding='utf-8', xml_declaration=True)
        return BinaryBytes(xml_formatted_str), False

    def _populate_declarations(self):
        self.ensure_one()
        for record in self:
            total_lines_created = 0
            for config in REPORT_CONFIG.values():
                if record[config['include_field']]:
                    report = record[config['relation_field']]
                    report.action_generate_declarations()
                    total_lines_created += report.lines_count
            if total_lines_created == 0:
                raise UserError(self.env._('There are no declarations to generate for the selected forms in the given period.'))

    def _generate_281_xml(self, is_test=False):
        self.ensure_one()
        self._populate_declarations()
        xml_file, generate_error = self._render_xml(is_test=is_test)
        if generate_error:
            self.error_message = generate_error
            self.state = 'error'
            return

        if is_test:
            self.test_xml_file = xml_file
            self.test_xml_filename = f"TEST_{self.year}_281.xml"
            success_state = 'draft'
        else:
            self.xml_file = xml_file
            self.xml_filename = f"{self.year}_281.xml"
            success_state = 'ready'
        self._validate_xml_content(xml_file.content, success_state=success_state)

    def action_generate_test_xml(self):
        self._generate_281_xml(is_test=True)

    def action_generate_xml(self):
        self.is_correction_needed = False
        self._generate_281_xml()

    def _get_declaration_write_values(self):
        return {
            'pdf_to_generate': True,
            'declaration_error': False,
        }

    def _get_target_declarations(self):
        self.ensure_one()
        res_ids = []
        for config in REPORT_CONFIG.values():
            if self[config['include_field']] and self[config['count_field']]:
                res_ids += self[config['relation_field']].ids
        if res_ids:
            return self.env['hr.payroll.employee.declaration'].search([
                ('res_id', 'in', res_ids)
            ])
        return self.env['hr.payroll.employee.declaration']

    def action_mark_as_done(self):
        self.ensure_one()
        if self.env.context.get('skip_validation', False):
            self.state = 'done'
            return
        if not self.reference:
            raise UserError(self.env._('The 281 sheet must have a Belcotax reference to be completed.'))
        declarations = self._get_target_declarations()
        if declarations:
            declarations.write(self._get_declaration_write_values())
            self.env.ref('hr_payroll.ir_cron_generate_payslip_pdfs')._trigger()
        self.state = 'done'

    def action_generate_xml_and_download_data(self):
        self.ensure_one()
        if not self.xml_file:
            self.action_generate_xml()
        return {
            'model': self._name,
            'id': self.id,
            'field': 'xml_file',
            'filename': self.xml_filename,
            'filename_field': 'xml_filename',
            'download': True,
        }

    def action_correct_declaration(self):
        self.ensure_one()

        # Check that the declaration has a reference from Belcotax
        if not self.reference:
            raise ValidationError(self.env._(
                "The declaration can't be corrected without providing the reference from Belcotax."
            ))

        existing_correction = self.search_count([('origin_id', '=', self.id)], limit=1)
        if existing_correction:
            raise ValidationError(
                self.env._("A correction declaration already exists for this declaration.")
            )

        # Collect included reports to copy
        reports_to_correct = []
        if self.include_281_10 and self.l10n_be_281_10_ids:
            reports_to_correct.append(self.l10n_be_281_10_ids)

        if self.include_281_45 and self.l10n_be_281_45_ids:
            reports_to_correct.append(self.l10n_be_281_45_ids)

        if self.include_281_18 and self.l10n_be_281_18_ids:
            reports_to_correct.append(self.l10n_be_281_18_ids)

        if self.include_281_20 and self.l10n_be_281_20_ids:
            reports_to_correct.append(self.l10n_be_281_20_ids)

        if self.include_281_30 and self.l10n_be_281_30_ids:
            reports_to_correct.append(self.l10n_be_281_30_ids)

        if not reports_to_correct:
            raise ValidationError(self.env._(
                "No forms to correct. Please ensure at least one form type is included."
            ))

        # Create correction declaration
        correction_declaration = self.copy({
            'type_sending': '1',  # Correction
            'type_treatment': '1',  # Modification
            'origin_id': self.id,
        })

        return {
            'name': self.env._('Correction of 281 - %s', self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'l10n_be.281_xx',
            'view_mode': 'form',
            'res_id': correction_declaration.id,
        }

    def action_cancel_declaration(self):
        self.ensure_one()
        self.state = 'cancel'

    def action_set_draft_declaration(self):
        self.ensure_one()
        self.test_xml_file = False
        self.test_xml_filename = False
        self.xml_file = False
        self.xml_filename = False
        self.state = 'draft'
