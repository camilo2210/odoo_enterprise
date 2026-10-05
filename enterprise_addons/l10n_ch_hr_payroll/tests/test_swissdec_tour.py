# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
from collections import Counter
from contextlib import contextmanager
from unittest.mock import patch

from odoo import Command
from odoo.tests import HttpCase, tagged

from odoo.addons.l10n_ch_hr_payroll.tests.swissdec_5_0 import TestSwissdec5Common

# salaries of the persons, by domain
SALARIES = {
    'AHV-AVS': ('AHV-AVS-Salaries', 'AHV-AVS-Salary'),
    'FAK-CAF': ('FAK-CAF-Salaries', 'FAK-CAF-Salary'),
    'BVG-LPP': ('BVG-LPP-Salaries', 'BVG-LPP-Salary'),
    'UVG-LAA': ('UVG-LAA-Salaries', 'UVG-LAA-Salary'),
    'UVGZ-LAAC': ('UVGZ-LAAC-Salaries', 'UVGZ-LAAC-Salary'),
    'KTG-AMC': ('KTG-AMC-Salaries', 'KTG-AMC-Salary'),
    'TaxAtSource': ('TaxAtSourceSalaries', 'TaxAtSourceSalary'),
    'TaxCrossborder': ('TaxCrossborderSalaries', 'TaxCrossborderSalary'),
}
# declared totals, that the institutions acknowledge in their receipt
QUITTANCES = {
    'AHV-AVS': ('AHV-AVS-Totals', 'AHV-AVS-QuittanceWithoutCompletion'),
    'FAK-CAF': ('FAK-CAF-Totals', 'FAK-CAF-QuittanceWithoutCompletion'),
    'UVG-LAA': ('UVG-LAA-Totals', 'UVG-LAA-QuittanceWithoutCompletion'),
    'UVGZ-LAAC': ('UVGZ-LAAC-Totals', 'UVGZ-LAAC-QuittanceWithoutCompletion'),
    'KTG-AMC': ('KTG-AMC-Totals', 'KTG-AMC-QuittanceWithoutCompletion'),
    'TaxAtSource': ('TaxAtSourceTotals', 'TaxAtSourceDeclarationQuittance'),
    'TaxCrossborder': ('TaxCrossborderTotals', 'TaxCrossborderQuittanceWithoutCompletion'),
}
TRANSMISSION_DATE = "2023-02-26 10:00:00"


def to_list(value):
    if not value:
        return []
    return value if isinstance(value, list) else [value]


def notification(description, quality_level, code):
    return {'Notification': [{'Description': description, 'QualityLevel': quality_level, 'DescriptionCode': code}]}


@tagged('post_install_l10n', 'post_install', '-at_install', 'swissdec_payroll')
class TestSwissdecTour(TestSwissdec5Common, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref('base.user_admin').write({
            'company_ids': [Command.link(cls.muster_ag_company.id)],
            'company_id': cls.muster_ag_company.id,
        })

    def _get_addressees(self, declaration):
        """ References of the institutions a declaration is addressed to, by domain; their canton for the tax. """
        addressees = {}
        for domain, institutions in declaration['Job']['Addressees'][0].items():
            if domain == 'Tax':
                persons = declaration['SalaryDeclaration']['Company']['Staff']['Person']
                addressees[domain] = sorted({person['Particulars']['ResidenceCanton'] for person in persons if 'TaxSalaries' in person})
            else:
                addressees[domain] = [institution['institutionIDRef'] for institution in to_list(institutions)]
        return addressees

    def _get_salaries(self, person, domain, reference):
        salaries_key, salary_key = SALARIES[domain]
        return [salary for salary in to_list(person.get(salaries_key, {}).get(salary_key)) if salary.get('institutionIDRef') == reference]

    def _get_persons(self, company, domain, reference):
        persons = company['Staff']['Person']
        if domain == 'Tax':
            return [person for person in persons if 'TaxSalaries' in person and person['Particulars']['ResidenceCanton'] == reference]
        return [person for person in persons if self._get_salaries(person, domain, reference)]

    def _get_status(self, job_key, declaration):
        """ Distributed to every institution, but the second AVS one, some of them asking for a completion. """
        job_state = {}
        for domain, references in self._get_addressees(declaration).items():
            job_state[domain] = []
            for position, reference in enumerate(references):
                state = {'canton' if domain == 'Tax' else 'institutionIDRef': reference}
                credentials = {'Credentials': {'Key': f"{job_key}|{domain}|{reference}", 'Password': "password"}}
                if domain == 'AHV-AVS' and position:
                    state['Error'] = {'EndUserInformation': "The institution could not be reached."}
                elif domain in ('UVG-LAA', 'Statistic'):
                    state['Success'] = {'CompletionAndResult': {'Completion': {'Url': "https://completion.example.com"}, **credentials}}
                else:
                    state['Success'] = {'Result': credentials}
                if domain == 'AHV-AVS' and not position:
                    state['Success']['ResponseState'] = {
                        'Code': 'acceptedWithWarning',
                        'Warning': notification("The accounting period is not valid.", 'Plausibility', 2013),
                    }
                job_state[domain].append(state)
        return {
            'JobFinished': True,
            'PlausibilityState': {'Plausible': {
                'JobState': job_state,
                'Info': notification("The declaration has been distributed.", 'Acceptance', 9999),
            }},
        }

    def _get_quittance(self, company, domain, reference, institution):
        if domain == 'Tax':
            persons = self._get_persons(company, domain, reference)
            return {'TaxQuittance': {
                'NumberOf-TaxSalary-Tags': sum(len(to_list(person['TaxSalaries'].get('TaxSalary'))) for person in persons),
                'NumberOf-TaxAnnuity-Tags': sum(len(to_list(person['TaxSalaries'].get('TaxAnnuity'))) for person in persons),
                'NumberOf-OwnershipRightDetail-Tags': 0,
            }}
        salary_totals = company.get('SalaryTotals')
        if domain not in QUITTANCES or not isinstance(salary_totals, dict):
            return {}
        totals_key, quittance_key = QUITTANCES[domain]
        totals = next((totals for totals in to_list(salary_totals.get(totals_key)) if totals['institutionIDRef'] == reference), None)
        if not totals:
            return {}
        quittance = {key: value for key, value in totals.items() if key != 'institutionIDRef'}
        if domain == 'UVG-LAA':
            sexes = Counter(person['Particulars'].get('Sex') for person in self._get_persons(company, domain, reference))
            quittance.update({'NumberOfFemalePersons': sexes['F'], 'NumberOfMalePersons': sexes['M']})
        elif domain == 'TaxCrossborder':
            quittance['TaxAtSourceCanton'] = institution.get('CantonID')
        return {quittance_key: quittance}

    def _get_tax_at_source_correction(self, salary, position):
        """ The first person has a month reversed, the second one has a tax scale to correct, and so on. """
        current = salary.get('Current', {})
        comment = {'Comment': notification("Please apply the new tax scale.", 'Comment', 3314)}
        if position % 2:
            correction = {'AwaitCorrectionFromCompany': {**comment, 'ValidAsOf': salary.get('CurrentMonth'), 'TaxAtSourceCategory': current.get('TaxAtSourceCategory')}}
        else:
            correction = {'Reversal': {**comment, 'Month': salary.get('CurrentMonth'), 'Old': current, 'New': {**current, 'TaxAtSource': "0.00"}}}
        return {
            'CurrentMonth': salary.get('CurrentMonth'),
            'TaxAtSourceCanton': salary.get('TaxAtSourceCanton'),
            'TaxAtSourceMunicipalityID': salary.get('TaxAtSourceMunicipalityID'),
            'Correction': [correction],
        }

    def _get_result_person(self, person, domain, reference, position):
        particulars = person['Particulars']
        result = {
            key: particulars[key]
            for key in ('Lastname', 'Firstname', 'Sex', 'DateOfBirth', 'Nationality', 'EmployeeNumber', 'Social-InsuranceIdentification')
            if key in particulars
        }
        result['Process'] = ('finished', 'manual', 'provisional')[position % 3]
        if position == 0:
            result['Warning'] = notification("The date of birth does not match the central register.", 'Plausibility', 2101)
        elif position == 1:
            result['Info'] = notification("The person will be checked manually.", 'Comment', 9999)
        salaries = self._get_salaries(person, domain, reference) if domain in SALARIES else []
        declaration_category = next((salary['DeclarationCategory'] for salary in salaries if salary.get('DeclarationCategory')), None)
        if declaration_category:
            result['DeclarationCategory'] = declaration_category
        if domain == 'BVG-LPP':
            result['Contributions'] = {'Contribution': [{
                'ValidAsOf': "2023-01-01",
                'BVG-LPP-Code': salary.get('BVG-LPP-Code', "A1"),
                'EmployeeContribution': f"{float(salary.get('BVG-LPP-AnnualBasis', 0)) * 0.035 / 12:.2f}",
                'EmployerContribution': f"{float(salary.get('BVG-LPP-AnnualBasis', 0)) * 0.045 / 12:.2f}",
            } for salary in salaries]}
        elif domain == 'TaxAtSource':
            result['TaxAtSourceSalaries'] = {'TaxAtSourceSalary': [self._get_tax_at_source_correction(salary, position) for salary in salaries]}
        return result

    def _get_result(self, declaration, domain, reference):
        """ Answer of the institution: the declared persons and totals, but for the statistic, waiting for its
        completion, and the second and third compensation funds, still processing or not supporting it. """
        company = declaration['SalaryDeclaration']['Company']
        position = self._get_addressees(declaration)[domain].index(reference)
        institution = next((
            institution for institution in to_list(company.get('Institutions', {}).get(domain))
            if institution.get('institutionID') == reference
        ), {})
        context = {'AddresseeContext': {
            'RequestID': reference,
            'ResponseID': f"{reference}-{position}",
            'InstitutionName': institution.get('InsuranceCompanyName') or reference,
            'TransmissionDate': TRANSMISSION_DATE,
            'UserAgent': {'Producer': "Swissdec", 'Name': "Reference Implementation", 'Version': "5.0", 'StandardVersion': "5.0", 'Certificate': "Certificate"},
        }}
        if domain == 'Statistic':
            answer = {'CompletionReleaseIsMissing': context}
        elif domain == 'FAK-CAF' and position == 1:
            answer = {'Processing': {**context, 'ExpectedAvailability': "2023-03-31"}}
        elif domain == 'FAK-CAF' and position == 2:
            answer = {'NotSupported': context}
        else:
            persons = self._get_persons(company, domain, reference)
            answer = {
                'Success': {
                    **context,
                    'Institution': institution,
                    'ChangesConsideredUpTo': "2023-02-01",
                    **self._get_quittance(company, domain, reference, institution),
                    'Staff': {'Person': [self._get_result_person(person, domain, reference, index) for index, person in enumerate(persons)]},
                },
                'Info': notification("The declaration has been received.", 'Acceptance', 9999),
            }
            if domain == 'Tax':
                answer['Success']['InstitutionCantonID'] = reference
        return {'SalaryResult': {domain: answer}, 'ResponseContext': {'DeclarationID': reference, 'TransmissionDate': TRANSMISSION_DATE}}

    @contextmanager
    def _mock_swissdec_transmission(self):
        """ Answer the Swissdec requests as the institutions would, from the data declared to them. """
        declarations = {}

        def swissdec_request(company, route, **kwargs):
            data = kwargs.get('data', {})
            if route == 'generate_tax_accounting_report':
                # one wage statement per person, from from_person to to_person (excluded)
                persons = to_list(data['SalaryDeclaration']['Company']['Staff']['Person'])
                return {'tax_accounting_reports': {
                    f"tax_accounting_pers_{person['Particulars']['EmployeeNumber']}.pdf": base64.b64encode(b"%PDF wage statement")
                    for person in persons[kwargs['from_person'] - 1:kwargs['to_person'] - 1]
                }}
            if route == 'declare_salary':
                job_key = f"JOB-{len(declarations) + 1}"
                declarations[job_key] = data
                response = {'JobKey': job_key, 'ResponseContext': {'DeclarationID': job_key, 'TransmissionDate': TRANSMISSION_DATE}}
            elif route == 'get_status_from_declare_salary':
                response = self._get_status(data['JobKey'], declarations[data['JobKey']])
            elif route == 'get_result_from_declare_salary':
                (identification,) = data['Domain'].values()
                job_key, domain, reference = identification['Key'].split('|')
                response = self._get_result(declarations[job_key], domain, reference)
            else:
                raise AssertionError(f"Unexpected Swissdec request: {route}")
            return {'soap_response': response, 'request_xml': f"<{route}/>", 'response_xml': f"<{route}_response/>"}

        with patch.object(self.registry['res.company'], '_l10n_ch_swissdec_request', swissdec_request):
            yield

    def _start_widgets_tour(self, action):
        self.start_tour(f"/odoo/action-{action}", 'l10n_ch_hr_payroll_swissdec_widgets', login='admin', timeout=600)

    def test_declaration_widgets(self):
        """ The salaries of every declaration of the Swissdec test cases are displayed. """
        for action in (
            'l10n_ch_hr_payroll.l10n_ch_yearly_retrospective_action',
            'l10n_ch_hr_payroll.l10n_ch_ema_declaration_action',
            'l10n_ch_hr_payroll.l10n_ch_st_declaration_action',
            'l10n_ch_hr_payroll.l10n_ch_statistic_declaration_action',
            'l10n_ch_hr_payroll.action_l10n_ch_certificate',
        ):
            with self.subTest(action=action):
                self._start_widgets_tour(action)

    def test_generate_wage_statement(self):
        """ The wage statement of a single employee is generated from the declaration and posted in its chatter. """
        declaration = self.yearly_retrospective_2022_12
        with self._mock_swissdec_transmission():
            self.start_tour(
                f"/odoo/action-l10n_ch_hr_payroll.l10n_ch_yearly_retrospective_action/{declaration.id}",
                'l10n_ch_hr_payroll_swissdec_wage_statement', login='admin', timeout=600,
            )

        self.env.invalidate_all()
        wage_statement = self.env['hr.payroll.employee.declaration'].search([
            ('res_model', '=', declaration._name),
            ('res_id', '=', declaration.id),
        ])
        self.assertEqual(len(wage_statement), 1)
        self.assertEqual(wage_statement.pdf_file.content, b"%PDF wage statement")
        attachment = declaration.message_ids[:1].attachment_ids
        self.assertEqual(attachment.name, f"{wage_statement.pdf_filename}.pdf")

    def test_declaration_result_widgets(self):
        """ The answers of the institutions to each kind of declaration are displayed. """
        declarations = (
            self.yearly_retrospective_2022_12,
            self.ema_declaration_2022_01,
            self.is_declaration_2022_06,
            self.statistic_declaration_2022_12,
            self.rectificate_2022_01,
            self.yearly_prospective_2023_01,
        )
        transmissions = self.env['l10n.ch.swissdec.declaration']
        with self._mock_swissdec_transmission():
            for declaration in declarations:
                transmission = transmissions.browse(declaration.action_declare_salary()['res_id'])
                transmission.get_status_from_declare_salary()
                transmission.l10n_ch_swissdec_job_result_ids.filtered('credential_key').action_get_result_from_declare_salary()
                transmissions |= transmission

        jobs = transmissions.l10n_ch_swissdec_job_result_ids
        self.assertEqual(set(transmissions.mapped('state')), {'finished'})
        self.assertEqual(set(jobs.mapped('domain')), {'AHV-AVS', 'FAK-CAF', 'BVG-LPP', 'UVG-LAA', 'UVGZ-LAAC', 'KTG-AMC', 'Tax', 'TaxAtSource', 'TaxCrossborder', 'Statistic'})
        self.assertEqual(set(jobs.mapped('general_state')), {'Success', 'Error'})
        self.assertEqual(set(jobs.filtered('credential_key').mapped('result_state')), {'Success', 'Processing', 'NotSupported', 'CompletionReleaseIsMissing'})

        for model, list_view, form_view in (
            ('l10n.ch.swissdec.declaration', 'l10n_ch_swissdec_declaration_tree', 'l10n_ch_swissdec_declaration_form'),
            ('l10n.ch.swissdec.job.result', 'view_l10n_ch_swissdec_job_result_tree', 'view_l10n_ch_swissdec_job_result_form'),
        ):
            action = self.env['ir.actions.act_window'].create({
                'name': model,
                'res_model': model,
                'view_ids': [
                    Command.create({'view_mode': 'list', 'view_id': self.env.ref(f'l10n_ch_hr_payroll.{list_view}').id}),
                    Command.create({'view_mode': 'form', 'view_id': self.env.ref(f'l10n_ch_hr_payroll.{form_view}').id}),
                ],
            })
            with self.subTest(model=model):
                self._start_widgets_tour(action.id)
