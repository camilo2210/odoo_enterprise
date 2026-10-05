# Part of Odoo. See LICENSE file for full copyright and licensing details.

# Source: https://www.socialsecurity.be/site_fr/employer/applics/dmfa/index.htm

import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from pprint import pformat

from odoo import api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError

import logging
import requests
import zipfile
import io

_logger = logging.getLogger(__name__)

ONSS_FILES = ['NOSSContributionRate_', 'NOSSWorkerAndContributionComb_']


class L10nBeOnssRatesImportWizard(models.TransientModel):
    _name = 'l10n.be.onss.rates.import.wizard'
    _description = 'Belgian Payroll: ONSS rates import wizard'

    onss_rates_file_ids = fields.One2many(
        'ir.attachment', 'res_id',
        domain=[('res_model', '=', 'l10n.be.onss.rates.import.wizard')],
        string='ONSS Rates Files')
    import_mode = fields.Selection(
        selection=[('manual', 'Manual File Import'), ('automatic', 'Automatic Import')],
        required=True, default='automatic')
    import_all = fields.Boolean(
        string='Import All', default=True,
        help='If this is checked, import all rates. Otherwise, import only new or updated rates.')
    import_up_to_today = fields.Boolean(
        string='Import Up to Today', default=True,
        help='If this is checked, import all rates since the year and quarter given up to today. '
             'Otherwise, import only for the quarter and year given')

    year = fields.Integer(
        default=lambda self: fields.Date.today().year,
        required=True,
        help='Year for which to download the onss rates file'
    )
    quarter = fields.Selection(
        selection=[('1', 'Q1'), ('2', 'Q2'), ('3', 'Q3'), ('4', 'Q4')],
        required=True,
        default=lambda self: str(self.month_to_quarter(fields.Date.today().month)),
        help='Quarter for which to download the onss rates file'
    )

    @api.model
    def quarter_to_month(self, quarter):
        return (quarter - 1) * 3 + 1

    @api.model
    def month_to_quarter(self, month):
        return (month - 1) // 3 + 1

    @api.model
    def get_year_quarter_from_filename(self, filename):
        filename_no_extension = filename[:-4]
        year, quarter = (int(x) for x in filename_no_extension.split('_')[1:3])
        return year, quarter

    def _parse_rates_file(self, filename, xml_file_bytes, year, quarter, employer_categories):
        try:
            tree = ET.parse(io.BytesIO(xml_file_bytes))
        except Exception:  # noqa: BLE001
            _logger.warning("Failed to parse the file %s", filename)
            return [], [], [], []
        root = tree.getroot()

        belgium = self.env.ref('base.be').id

        rp_xmlids = []
        rp_vals = []

        rpv_xmlids = []
        rpv_vals = []

        for child in root:
            if child.tag == 'ContributionRate':
                if not self.import_all and child.find('Status') is None:
                    continue

                employer_class = child.find('EmployerClass').text
                if child.find('ContributionWorkerCode') is not None:
                    worker_code = child.find('ContributionWorkerCode').text
                elif child.find('UnrelatedWorkerCode') is not None:
                    worker_code = child.find('UnrelatedWorkerCode').text
                else:
                    worker_code = child.find('WorkerCode').text
                contribution_type = child.find('ContributionType').text
                personal_rate = float(child.find('PersonalRate').text)
                employer_rate = float(child.find('EmployerRate').text)
                salary_moderation_rate = float(child.find('SalaryModerationRate').text)
                total_rate = float(child.find('TotalRate').text)

                if employer_class in employer_categories:
                    rp_xmlids.append(f'rule_parameter_l10n_be_onss_rates_{employer_class}_{worker_code}_{contribution_type}')
                    rp_vals.append({
                        'name': self.env._('ONSS Rates: Employer Class (%(ec)s) - '
                                           'Worker Code (%(wc)s) - Contribution Type (%(ct)s)',
                                           ec=employer_class, wc=worker_code, ct=contribution_type),
                        'code': f'l10n_be_onss_rates_{employer_class}_{worker_code}_{contribution_type}',
                        'country_id': belgium,
                    })

                    rpv_xmlids.append(f'rule_parameter_value_l10n_be_onss_rates_{employer_class}_{worker_code}_{contribution_type}_{year}_{quarter}')
                    rpv_vals.append({
                        'parameter_value': str({
                            'personal_rate': personal_rate,
                            'employer_rate': employer_rate,
                            'salary_moderation_rate': salary_moderation_rate,
                            'total_rate': total_rate,
                        }),
                        'date_from': datetime(year, self.quarter_to_month(quarter), 1).date(),
                    })
        return rp_xmlids, rp_vals, rpv_xmlids, rpv_vals

    def _parse_combination_file(self, filename, xml_file_bytes, year, quarter, employer_categories):
        try:
            tree = ET.parse(io.BytesIO(xml_file_bytes))
        except Exception:  # noqa: BLE001
            _logger.warning("Failed to parse the file %s", filename)
            return [], [], [], []
        root = tree.getroot()

        belgium = self.env.ref('base.be').id

        rp_xmlids = []
        rp_vals = []

        rpv_xmlids = []
        rpv_vals = []

        already_parsed = []
        worker_codes_by_emp_cat = defaultdict(set)
        for child in root:
            if child.tag == 'WorkerAndContributionComb':
                employer_class = child.find('EmployerClass').text
                worker_code = child.find('WorkerCode').text
                contribution_worker_code = child.find('ContributionWorkerCode').text
                owedness_codes = [code.text for code in child.findall('OwednessCode')]

                worker_codes_by_emp_cat[employer_class].add(worker_code)
                if employer_class in employer_categories and (employer_class, worker_code) not in already_parsed:
                    rp_xmlids.append(f'rule_parameter_l10n_be_onss_combinations_{employer_class}_{worker_code}')
                    rp_vals.append({
                        'name': self.env._('ONSS Combinations: Employer Class (%(ec)s) - Worker Code (%(wc)s)',
                                           ec=employer_class, wc=worker_code),
                        'code': f'l10n_be_onss_combinations_{employer_class}_{worker_code}',
                        'description': '{contribution_worker_code: [owedness_codes]}',
                        'country_id': belgium,
                    })

                    rpv_xmlids.append(f'rule_parameter_value_l10n_be_onss_combinations_{employer_class}_{worker_code}_{year}_{quarter}')
                    rpv_vals.append({
                        'parameter_value': {contribution_worker_code: owedness_codes},
                        'date_from': datetime(year, self.quarter_to_month(quarter), 1).date(),
                    })

                    already_parsed.append((employer_class, worker_code))
                elif (employer_class, worker_code) in already_parsed:
                    rpv_vals[-1]['parameter_value'][contribution_worker_code] = owedness_codes

        for val in rpv_vals:
            val['parameter_value'] = pformat(val['parameter_value'])
        return rp_xmlids, rp_vals, rpv_xmlids, rpv_vals, worker_codes_by_emp_cat

    def _create_rule_parameters(self, rp_xmlids, rp_vals):
        rp_ids_by_xmlid = {name: res_id[0] for name, res_id in dict(self.env['ir.model.data']._read_group(
            domain=[
                ('name', 'in', rp_xmlids),
                ('module', '=', 'l10n_be_hr_payroll'),
                ('model', '=', 'hr.rule.parameter')
            ],
            groupby=['name'],
            aggregates=['res_id:array_agg'],
        )).items()}

        for i in range(len(rp_xmlids) - 1, -1, -1):
            if rp_xmlids[i] in rp_ids_by_xmlid:
                rp_vals.pop(i)
                rp_xmlids.pop(i)

        # if we have rule parameters to create
        if rp_vals:
            rp_ids = self.env['hr.rule.parameter'].create(rp_vals).ids

            ir_model_data_vals = []
            for i in range(len(rp_ids)):
                rp_ids_by_xmlid[rp_xmlids[i]] = rp_ids[i]
                ir_model_data_vals.append({
                    'name': rp_xmlids[i],
                    'module': 'l10n_be_hr_payroll',
                    'res_id': rp_ids[i],
                    'model': 'hr.rule.parameter',
                    # noupdate is set to true to avoid deleting the record at module update
                    'noupdate': True,
                })
            self.env['ir.model.data'].create(ir_model_data_vals)
        return rp_ids_by_xmlid

    def _create_rule_parameter_values(self, rp_ids_by_xmlid, rpv_xmlids, rpv_vals, date_string_size=7):
        rpv_ids_by_xmlid = {name: res_id[0] for name, res_id in dict(self.env['ir.model.data']._read_group(
            domain=[
                ('name', 'in', rpv_xmlids),
                ('module', '=', 'l10n_be_hr_payroll'),
                ('model', '=', 'hr.rule.parameter.value')
            ],
            groupby=['name'],
            aggregates=['res_id:array_agg'],
        )).items()}

        rpv_ids = list(rpv_ids_by_xmlid.values())
        existing_rule_parameter_values_by_id = {
            record.id: record for record in
            self.env['hr.rule.parameter.value'].search([('id', 'in', rpv_ids)])
        }
        for i in range(len(rpv_xmlids) - 1, -1, -1):
            if rpv_xmlids[i] in rpv_ids_by_xmlid:
                rpv_id = rpv_ids_by_xmlid[rpv_xmlids[i]]
                rpv = existing_rule_parameter_values_by_id[rpv_id]
                rpv.parameter_value = rpv_vals.pop(i)['parameter_value']
                rpv_xmlids.pop(i)

        # if we have rule parameter values to create
        if rpv_vals:
            # we need to get all the rule_parameter_id in the same order as the vals to create the values in batch
            # remove the _{year}_{quarter} from a value xmlid to get the rule parameter
            rp_xmlids = [xmlid[:-date_string_size].replace('value_', '') for xmlid in rpv_xmlids]
            for i in range(len(rp_xmlids)):
                rpv_vals[i]['rule_parameter_id'] = rp_ids_by_xmlid[rp_xmlids[i]]

            rpv_ids = self.env['hr.rule.parameter.value'].create(rpv_vals).ids

            ir_model_data_vals = []
            for i in range(len(rpv_ids)):
                ir_model_data_vals.append({
                    'name': rpv_xmlids[i],
                    'module': 'l10n_be_hr_payroll',
                    'res_id': rpv_ids[i],
                    'model': 'hr.rule.parameter.value',
                    # noupdate is set to true to avoid deleting the record at module update
                    'noupdate': True,
                })
            self.env['ir.model.data'].create(ir_model_data_vals)

    def _update_employer_category_worker_codes(self, worker_codes_by_emp_cat):
        for employer_dmfa_code, worker_dmfa_codes in worker_codes_by_emp_cat.items():
            employer_category = self.env['l10n.be.employer.category'].search([('dmfa_code', '=', employer_dmfa_code)], limit=1)
            if not employer_category:
                continue
            worker_codes = self.env['l10n.be.worker.code'].search([('dmfa_code', 'in', list(worker_dmfa_codes))])
            employer_category.allowed_worker_code_ids = worker_codes

    def action_import_files(self):
        self.ensure_one()
        if not self.onss_rates_file_ids:
            _logger.warning("No files to import")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'message': self.env._('No files imported'),
                    'sticky': False,
                }
            }

        employer_categories = self.env.companies.current_payroll_config_id.l10n_be_employer_category_id.mapped('dmfa_code')
        if not employer_categories:
            raise UserError(self.env._('Please first set the employer category on your company in the Payroll Settings.'))

        for file in self.onss_rates_file_ids:
            try:
                with zipfile.ZipFile(io.BytesIO(file.raw), 'r') as z:
                    for filename in z.namelist():
                        if filename.endswith('.xml') and filename.startswith('NOSSContributionRate_'):
                            _logger.info("Parsing file %s", filename)
                            year, quarter = self.get_year_quarter_from_filename(filename)
                            rp_xmlids, rp_vals, rpv_xmlids, rpv_vals = self._parse_rates_file(filename, z.read(filename), year, quarter, employer_categories)
                            rp_ids_by_xmlid = self.with_user(SUPERUSER_ID)._create_rule_parameters(rp_xmlids, rp_vals)
                            self.with_user(SUPERUSER_ID)._create_rule_parameter_values(rp_ids_by_xmlid, rpv_xmlids, rpv_vals)
                            _logger.info("Imported file %s", filename)

                        elif filename.endswith('.xml') and filename.startswith('NOSSWorkerAndContributionComb_'):
                            _logger.info("Parsing file %s", filename)
                            year, quarter = self.get_year_quarter_from_filename(filename)
                            rp_xmlids, rp_vals, rpv_xmlids, rpv_vals, worker_codes_by_emp_cat = self._parse_combination_file(filename, z.read(filename), year, quarter, employer_categories)
                            rp_ids_by_xmlid = self.with_user(SUPERUSER_ID)._create_rule_parameters(rp_xmlids, rp_vals)
                            self.with_user(SUPERUSER_ID)._create_rule_parameter_values(rp_ids_by_xmlid, rpv_xmlids, rpv_vals)
                            self._update_employer_category_worker_codes(worker_codes_by_emp_cat)
                            _logger.info("Imported file %s", filename)
            except zipfile.BadZipFile:
                pass

        next_action = {'type': 'ir.actions.client', 'tag': 'reload'}
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': self.env._('The ONSS rates have been successfully imported'),
                'sticky': False,
                'next': next_action,
            }
        }

    def _download_file(self, year, quarter):
        """
        1. Build the URL.
        2. Download the ZIP from ONSS.
        3. Attach it to this wizard record.
        """
        url = self._build_onss_download_url(year, quarter)
        _logger.info("Downloading ONSS rates ZIP from %s", url)

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            filename = url.split('/')[-1]
            self.env['ir.attachment'].create({
                'name': filename,
                'res_model': self._name,
                'res_id': self.id,
                'raw': response.content,
                'mimetype': 'text/plain',
            })
            _logger.info("Attached file %s to wizard", filename)
        except Exception:  # noqa: BLE001
            _logger.error("Failed to download from %s", url)

    def action_import_from_website(self):
        self.ensure_one()
        if self.import_up_to_today:
            return self._fetch_onss_rates_since(self.year, int(self.quarter))
        else:
            self._download_file(self.year, self.quarter)
            return self.action_import_files()

    @api.model
    def _get_year_quarter(self, date):
        return str(date.year), str(self.month_to_quarter(date.month))

    @api.model
    def _get_filename(self, year, quarter):
        return f'dmfa_rate_{year}_{quarter}.zip'

    @api.model
    def _build_onss_download_url(self, year, quarter):
        """
        Return the official ONSS zip file URL based on year and quarter.
        """
        filename = self._get_filename(year, quarter)
        return f'https://www.socialsecurity.be/site_fr/employer/applics/dmfa/documents/zip/{filename}'

    @api.model
    def _fetch_onss_rates_since(self, year, quarter):
        """
        Import all the onss rates since the year and quarter given until today
        """
        wizard = self.env['l10n.be.onss.rates.import.wizard'].create([{}])
        today_year, today_quarter = wizard.year, int(wizard.quarter)

        # First, import the whole file for the year and quarter given
        wizard.import_all = True
        wizard._download_file(year, quarter)
        wizard.action_import_files()
        wizard.onss_rates_file_ids = False

        # Then, import only changes up to today
        wizard.import_all = False
        while year < today_year or (year == today_year and quarter <= today_quarter):
            wizard._download_file(year, quarter)
            quarter += 1
            if quarter > 4:
                quarter = 1
                year += 1
        return wizard.action_import_files()

    @api.model
    def _cron_fetch_onss_rates(self):
        self.env['l10n.be.onss.rates.import.wizard']._fetch_onss_rates_since(datetime.today().year - 1, 1)
