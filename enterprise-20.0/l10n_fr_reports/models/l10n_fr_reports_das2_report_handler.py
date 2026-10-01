import re

from odoo import fields, models
from odoo.exceptions import UserError, RedirectWarning
from odoo.tools import SQL

DAS2_TAGS_MAP = {
    'l10n_fr_reports.account_tag_das2_fees': 'H',
    'l10n_fr_reports.account_tag_das2_commissions': 'C',
    'l10n_fr_reports.account_tag_das2_brokerage': 'CO',
    'l10n_fr_reports.account_tag_das2_rebates': 'R',
    'l10n_fr_reports.account_tag_das2_attendance_fees': 'JP',
    'l10n_fr_reports.account_tag_das2_copyright': 'DA',
    'l10n_fr_reports.account_tag_das2_inventor_rights': 'DI',
    'l10n_fr_reports.account_tag_das2_other_remuneration': 'AR',
    'l10n_fr_reports.account_tag_das2_benefit_in_kind': 'benefits_in_kind',
    'l10n_fr_reports.account_tag_das2_indemnities_refunds': 'indemnities_refunds',
    'l10n_fr_reports.account_tag_das2_withholding_tax': 'withholding_tax',
}

THRESHOLD_DAS2_REPORT = 2400  # in euros. Totals below this threshold are not reported.

NON_FR_STREET_PATTERN_START = re.compile(r'^(?P<num>\d+[A-Za-z0-9]?)\s+(?P<rest>.*)$')
NON_FR_STREET_PATTERN_END = re.compile(r'^(?P<rest>.*\D)\s+(?P<num>\d+[A-Za-z0-9]?)$')

FUNCTIONAL_GROUP_TYPE = 'INFENT'
DECLARATION_TYPE = 'HON'
DECLARATION_REFERENCE = 'INFENT000000000001'  # internal reference to the emitor
DECLARATION_RECEIVER = 'DGI_EDI_PART'
DECLARATION_WRITER_TYPE = 'ENT_EDI_PART'
DECLARATION_MILLESIME = '26'

DAS2_TAG_IDS = [
    'account_tag_das2_fees',
    'account_tag_das2_commissions',
    'account_tag_das2_brokerage',
    'account_tag_das2_rebates',
    'account_tag_das2_attendance_fees',
    'account_tag_das2_copyright',
    'account_tag_das2_inventor_rights',
    'account_tag_das2_other_remuneration',
    'account_tag_das2_benefit_in_kind',
    'account_tag_das2_indemnities_refunds',
    'account_tag_das2_withholding_tax',
]


class L10nFrDAS2ReportHandler(models.AbstractModel):
    _name = 'l10n_fr.das2.report.handler'
    _inherit = 'account.report.custom.handler'
    _description = 'DAS2 Report Custom Handler'

    def _get_das2_tags(self):
        tags = self.env['account.account.tag']
        for external_id in DAS2_TAG_IDS:
            tags += self.env.ref(f'l10n_fr_reports.{external_id}')
        return tags

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        options['das2_tag_ids'] = []  # we need to set a default value as it's used downstream
        if self.env.company.account_fiscal_country_id.code != 'FR':
            return

        options.setdefault('buttons', []).append({
            'name': self.env._("EDI DAS2"),
            'action': 'l10n_fr_reports_open_das2_wizard',
        })
        options['das2_tag_ids'] = self._get_das2_tags().ids
        options['custom_display_config'] = {
            'templates': {
                'AccountReportLineName': 'l10n_fr_reports.DAS2LineName',
            },
        }

    def _get_custom_groupby_map(self):
        return {
            'das2_tag_id': {
                'model': 'account.account.tag',
                'domain_builder': lambda grouping_key: [('account_id.tag_ids', '=', grouping_key)],
            },
        }

    def action_audit_cell(self, options, params):
        """ Override to show only move lines linked to DAS2-tagged accounts. """
        report = self.env['account.report'].browse(options['report_id'])
        action = report.action_audit_cell(options, params)

        action['domain'] = fields.Domain.AND([
            action['domain'],
            [
                ('account_id.tag_ids', 'in', options['das2_tag_ids']),
                ('move_id.move_type', 'in', self.env['account.move'].get_purchase_types()),
            ],
        ])

        return action

    def _custom_line_postprocessor(self, report, options, lines):
        lines = super()._custom_line_postprocessor(report, options, lines)

        for line in lines:
            # We only allow auditing the dynamically added lines
            if line.code == 'das2_report_total' and line.columns:
                line.columns[0].auditable = False

        return lines

    def _report_engine_das2(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        def _format_results(data):
            if not current_groupby:
                return {'total': sum(line['total'] for line in data) or 0.0, 'has_sublines': True}
            if current_groupby == 'partner_id':
                return [(line['partner_id'], {'total': line['total'], 'has_sublines': True}) for line in data]
            if current_groupby == 'das2_tag_id':
                return [(line['tag_id'], {'total': line['total'], 'has_sublines': True}) for line in data]
            return []

        report = self.env['account.report'].browse(options['report_id'])

        query = report._get_report_query(options, date_scope)
        query.add_join(
            kind='JOIN',
            alias='account_move_rel',
            table='account_move',
            condition=SQL("account_move_rel.id = account_move_line.move_id"),
        )
        query.add_join(
            kind='JOIN',
            alias='res_partner_rel',
            table='res_partner',
            condition=SQL("res_partner_rel.id = account_move_line.partner_id"),
        )

        selected_fields = SQL("""
            MIN(account_move_line.partner_id) AS partner_id,
            SUM(account_move_line.balance) AS total
        """)
        groupby_expression = SQL('GROUP BY account_move_line.partner_id')
        having_expression = SQL('HAVING SUM(account_move_line.balance) >= %(threshold)s', threshold=THRESHOLD_DAS2_REPORT)
        tag_alias_filter = SQL('')

        if current_groupby == 'das2_tag_id':
            # Only join to tags if grouping by tags to avoid duplication in other groupbys
            query.add_join(
                kind='JOIN',
                alias='account_account_account_tag_alias',
                table='account_account_account_tag',
                condition=SQL("account_account_account_tag_alias.account_account_id = account_move_line.account_id"),
            )

            tag_alias_filter = SQL(
                'AND account_account_account_tag_alias.account_account_tag_id = ANY(%(tag_ids)s)',
                tag_ids=options['das2_tag_ids'],
            )

            selected_fields = SQL("""
                account_account_account_tag_alias.account_account_tag_id AS tag_id,
                SUM(account_move_line.balance) AS total
            """)
            groupby_expression = SQL("""
                GROUP BY account_account_account_tag_alias.account_account_tag_id
            """)
            having_expression = SQL('')  # no threshold on tag level

        tag_exists_subquery = SQL("""
            EXISTS (
                SELECT 1
                FROM account_account_account_tag aaat
                WHERE aaat.account_account_id = account_move_line.account_id
                AND aaat.account_account_tag_id = ANY(%(tag_ids)s)
            )
        """, tag_ids=options['das2_tag_ids'])

        query = SQL(
            """
                SELECT %(selected_fields)s
                FROM %(from_clause)s
                WHERE %(where_clause)s
                AND res_partner_rel.l10n_fr_profession_id IS NOT NULL
                AND %(tag_exists_subquery)s
                %(tag_alias_filter)s
                AND account_move_rel.move_type = ANY(%(purchase_type)s)
                %(groupby_expression)s
                %(having_expression)s
            """,
            selected_fields=selected_fields,
            from_clause=query.from_clause,
            where_clause=query.where_clause,
            tag_exists_subquery=tag_exists_subquery,
            tag_alias_filter=tag_alias_filter,
            purchase_type=self.env['account.move'].get_purchase_types(),
            groupby_expression=groupby_expression,
            having_expression=having_expression,
        )

        self.env.cr.execute(query)
        return {next(iter(formulas_dict.values())):  _format_results(self.env.cr.dictfetchall())}

    def l10n_fr_reports_open_das2_wizard(self, options):
        if options['date']['period_type'] != 'year':
            raise UserError(self.env._("The DAS2 report can only be generated for a full fiscal year."))
        return self.env['l10n_fr.send.das2.report']._get_records_action(
            name=self.env._("DAS2 Report Generation"),
            target='new',
            context={**self.env.context, 'default_year': fields.Date.from_string(options.get('date', {}).get('date_from')).year},
        )

    def _get_partner_missing_fields(self, partner):
        errors = []
        name = partner.display_name

        checks = [
            (not partner.street, self.env._("partner '%s' street address is not set")),
            (not partner.zip, self.env._("partner '%s' zip code is not set")),
            (partner.is_company and not partner.l10n_fr_siret, self.env._("partner '%s' SIRET is not set")),
            (not partner.l10n_fr_profession_id, self.env._("partner '%s' profession is not set")),
            (not partner.city, self.env._("partner '%s' city is not set")),
            (not partner.country_id, self.env._("partner '%s' country is not set")),
        ]

        for condition, message in checks:
            if condition:
                errors.append(message % name)  # using classic string formatting here to avoid _ misuse

        if partner.country_code != 'FR' and 'EU' in (partner.country_id.country_group_codes or {}) \
            and not partner.is_company and not partner.birth_date:
            errors.append(self.env._("partner '%s' birth date is required for EU non-French residents", name))

        return errors

    def _raise_required_fields_errors(self, errors):
        button_label = ""
        action = {}

        if error_messages := errors['partner']['errors']:
            required_field_view_list = self.env.ref('l10n_fr_reports.view_partner_das2_required_partner_fields')
            required_field_view_form = self.env.ref('l10n_fr_reports.view_partner_form_inherit_das2_required_partner_fields')
            button_label = self.env._("Update vendors")
            action = errors['partner']['records']._get_records_action(
                name=self.env._("Missing partner data"),
                views=[(required_field_view_list.id, 'list'), (required_field_view_form.id, 'form')],
                domain=[('id', 'in', errors['partner']['records'].ids)],
            )
        elif error_messages := errors['account_representative']['errors']:
            required_field_view_form = self.env.ref('l10n_fr_reports.view_partner_form_inherit_das2_required_firm_fields')
            button_label = self.env._("Update account representative")
            action = errors['account_representative']['record']._get_records_action(
                name=self.env._("Missing account representative data"),
                views=[(required_field_view_form.id, 'form')],
            )
        elif error_messages := errors['contact_person']['errors']:
            required_contact_person_view = self.env.ref('l10n_fr_reports.view_partner_form_inherit_das2_required_contact_person_fields')
            button_label = self.env._("Update contact person")
            action = errors['contact_person']['record']._get_records_action(
                name=self.env._("Missing contact person data"),
                views=[(required_contact_person_view.id, 'form')],
            )
        elif error_messages := errors['company']['errors']:
            required_company_fields_view = self.env.ref('l10n_fr_reports.view_company_form_inherit_das2_required_fields')
            button_label = self.env._("Update company information")
            action = errors['company']['record']._get_records_action(
                views=[(required_company_fields_view.id, 'form')],
            )

        if error_messages:
            raise RedirectWarning(
                self.env._("DAS2 cannot be generated due to missing or misconfigured fields: \n%s", "\n".join(error_messages)),
                action,
                button_label,
            )

    def _check_required_fields(self, partners, contact_person):
        company = self.env.company
        account_representative = company.account_representative_id

        company_errors = []
        company_checks = [
            (not company.partner_id.l10n_fr_siret, self.env._("company SIRET is not set")),
            (not company.street, self.env._("company street address is not set")),
            (not company.zip, self.env._("company zip code is not set")),
            (not company.city, self.env._("company city is not set")),
            (not company.country_id, self.env._("company country is not set")),
            (not company.ape, self.env._("company APE code is not set")),
            (not company.l10n_fr_das2_activity, self.env._("company DAS2 activity is not set")),
        ]
        company_errors.extend(message for condition, message in company_checks if condition)

        account_representative_errors = []
        if account_representative:
            representative_checks = [
                (not account_representative.l10n_fr_siret, self.env._("account representative SIRET is not set")),
                (not account_representative.street, self.env._("account representative street address is not set")),
                (not account_representative.zip, self.env._("account representative zip code is not set")),
                (not account_representative.city, self.env._("account representative city is not set")),
                (not account_representative.country_id, self.env._("account representative country is not set")),
            ]
            account_representative_errors.extend(message for condition, message in representative_checks if condition)

        contact_person_errors = []
        if not contact_person:
            contact_person_errors.append(self.env._("a point of contact is not set"))
        else:
            if not contact_person.email:
                contact_person_errors.append(self.env._("point of contact email is not set"))
            if not contact_person.phone:
                contact_person_errors.append(self.env._("point of contact phone number is not set"))

        partner_errors = []
        invalid_partners = self.env['res.partner']
        for partner in partners:
            errors = self._get_partner_missing_fields(partner)
            if errors:
                partner_errors.extend(errors)
                invalid_partners |= partner

        return {
            'partner': {
                'errors': partner_errors,
                'records': invalid_partners,
            },
            'account_representative': {
                'errors': account_representative_errors,
                'record': account_representative,
            },
            'contact_person': {
                'errors': contact_person_errors,
                'record': contact_person,
            },
            'company': {
                'errors': company_errors,
                'record': company,
            },
        }

    def _extract_street_number(self, street):
        if not street:
            return "0000", None

        match = NON_FR_STREET_PATTERN_START.match(street)
        if match:
            return match.group("num").strip(), match.group("rest").strip()

        match = NON_FR_STREET_PATTERN_END.match(street)
        if match:
            return match.group("num").strip(), match.group("rest").strip()

        return "0000", street

    def _get_das2_totals(self, options):
        """ Calculates the sums per DAS2 tag and per partner needed for the DAS2 report.

            Returns a dict of the form:
            {
                'tags': {
                    tag_id: total_amount,
                },
                'partners': {
                    partner_id: {
                        tag_id: total_amount,
                    },
                }
            }
        """
        report = self.env['account.report'].browse(options['report_id'])
        options['unfold_all'] = True
        lines = report._get_lines(options)

        totals = {'tags': {}, 'partners': {}}

        for line in lines:
            res_ids = report._get_res_ids_from_line_id(
                line.id,
                target_model_names=[
                    'res.partner',
                    'account.account.tag',
                ],
            )

            # Only consider lines that have both a partner and a DAS2 tag linked
            if len(res_ids) == 2:
                partner_id = res_ids['res.partner']
                tag_id = res_ids['account.account.tag']
                amount = line.columns[0].no_format  # There's only 1 column

                totals['tags'][tag_id] = totals['tags'].get(tag_id, 0) + amount
                totals['partners'].setdefault(partner_id, {})
                totals['partners'][partner_id][tag_id] = (
                    totals['partners'][partner_id].get(tag_id, 0) + amount
                )

        return totals

    def _get_writer_edi_data(self):
        writer = self.env.company.account_representative_id or self.env.company.partner_id
        zip = writer.zip.zfill(5)

        writer_data = {
            'identifier': writer.l10n_fr_siret,
            'type': DECLARATION_WRITER_TYPE,
            'designation': writer.name[:35],
            'designation2': writer.name[35:70],
            'address': {
                'street_number': writer.street_number or "0000",
                'street_name': writer.street_name[:32],
                'zip': zip,
                'country_code': writer.country_code,
                'commune_name': writer.city[:26],
            },
            'reference': writer.l10n_fr_siret,
        }

        return writer_data

    def _get_remuneration_zones(self, amounts_by_tag_id, tags_external_ids):
        das2_codes = []
        das2_totals_per_code = []
        das2_global_totals = {
            'benefits_in_kind': 0,
            'indemnities_refunds': 0,
            'withholding_tax': 0,
        }

        for tag_id, amount in sorted((amounts_by_tag_id or {}).items()):  # sorting to have a deterministic order based on tags
            code = DAS2_TAGS_MAP[tags_external_ids[tag_id]]
            rounded = round(amount)
            if code in das2_global_totals:
                das2_global_totals[code] += rounded
            else:
                das2_codes.append(code)
                das2_totals_per_code.append(rounded)

        return das2_codes, das2_totals_per_code, das2_global_totals

    def _get_debtor_edi_data(self, totals, dads_year):
        company = self.env.company
        company_partner = self.env.company.partner_id  # used for address fields (base_address_extended)

        tags_external_ids = self.env['account.account.tag'].browse(list(totals['tags'].keys())).get_external_id()
        das2_codes, das2_totals_per_code, das2_global_totals = self._get_remuneration_zones(totals['tags'], tags_external_ids)

        company_data = {
            'identifier': company.partner_id.l10n_fr_siret[:14],
            'designation': company.name[:35],
            'designation2': company.name[35:50],
            'activity': company.l10n_fr_das2_activity[:40],
            'ape': company.ape[:5],
            'fiscal_year_end': f'{int(company.fiscalyear_last_month):02d}{int(company.fiscalyear_last_day):02d}',
            'address': {
                'commune_name': company_partner.city[:26],
                'country_code': company_partner.country_code,
                'street_name': company_partner.street_name[:32],
                'zip': company_partner.zip.zfill(5),
            },
            'das2_codes': das2_codes,
            'das2_totals_per_code': das2_totals_per_code,
            'das2_global_totals': das2_global_totals,
            'dads_year': dads_year,
            'date_from': f'{dads_year}0101',
            'date_to': f'{dads_year}1231',
        }

        if company_partner.street2:
            company_data['address']['street2'] = company_partner.street2[:32]

        if company_partner.street_number:
            company_data['address']['street_number'] = company_partner.street_number[:35]
        else:
            company_data['address']['street_number'] = '0000'

        if company_partner.street_number2:
            company_data['address']['street_type'] = company_partner.street_number2

        return company_data

    def _get_beneficiaries_edi_data(self, totals):
        beneficiaries = []
        partners = self.env['res.partner'].browse(list(totals['partners'].keys()))
        tags_external_ids = self.env['account.account.tag'].browse(list(totals['tags'].keys())).get_external_id()

        for partner in partners:
            das2_codes, das2_totals_per_code, das2_global_totals = self._get_remuneration_zones(
                totals['partners'][partner.id],
                tags_external_ids,
            )
            zip = partner.zip.zfill(5)

            beneficiary = {
                'is_company': partner.is_company,
                'is_european': "EU" in (partner.country_id.country_group_codes or {}),
                'identifier': partner.l10n_fr_siret,
                'designation': partner.name[:35],
                'designation2': partner.name[35:50],
                'address': {
                    'street_number': partner.street_number or '0000',
                    'street_type': partner.street_number2 or '',
                    'street_name': partner.street_name[:32],
                    'street2': (partner.street2 or '')[:32],
                    'commune_name': partner.city[:26],
                    'zip': zip,
                    'country_code': partner.country_code,
                    'country_name': partner.country_id.name,
                },
                'profession': partner.l10n_fr_profession_id.name[:40],
                'das2_codes': das2_codes,
                'das2_totals_per_code': das2_totals_per_code,
                'das2_global_totals': das2_global_totals,
            }

            if partner.birth_date:
                beneficiary["birth_date"] = partner.birth_date.strftime("%Y%m%d")

            if partner.street and partner.country_code != 'FR':
                number, street = self._extract_street_number(partner.street)
                if number:
                    beneficiary['address']['street_number'] = number
                beneficiary['address']['street_name'] = street[:32]

            beneficiaries.append(beneficiary)

        return beneficiaries

    def _fetch_insee_codes(self, country_codes, zip_codes):
        db_uuid = self.env['ir.config_parameter'].sudo().get_str('database.uuid')
        endpoint = self.env['account.report.async.document']._get_aspone_endpoint()

        response = self.env['account.report.async.document']._get_fr_webservice_answer(
            url=f"{endpoint}/api/l10n_fr_aspone/1/get_insee_code",
            params={
                'db_uuid': db_uuid,
                'lookups': [('res.country', list(country_codes)), ('res.city', list(zip_codes))],
            },
        )

        if not response['success']:
            raise UserError(self.env._("Failed to retrieve INSEE codes: %s", response))

        return response['data']['insee_map']

    def _inject_insee_codes(self, edi_values):
        beneficiaries = edi_values.get("beneficiaries") or []
        country_codes = set()
        zip_codes = set()

        for beneficiary in beneficiaries:
            address = beneficiary['address']
            country_code = address['country_code']

            if country_code != 'FR':
                country_codes.add(country_code)
            else:
                zip_codes.add(address['zip'])

        insee_map = self._fetch_insee_codes(country_codes, zip_codes)

        for beneficiary in beneficiaries:
            address = beneficiary['address']
            country_code = address['country_code']

            if country_code != 'FR':
                address['insee_country_code'] = insee_map.get(country_code)
            else:
                address['insee_zip'] = insee_map.get(address['zip'])

        return edi_values

    def _format_phone_number(self, phone):
        # sanitizes French numbers otherwise returns the maximum amount of digits possible
        sanitized_phone = re.sub(r'\D', '', phone or '')
        if sanitized_phone.startswith(('0033', '33')):
            sanitized_phone = '0' + sanitized_phone[-9:]
        return sanitized_phone[-10:]

    def _prepare_edi_values(self, options, contact_person, dads_year, is_test=False):
        totals = self._get_das2_totals(options)
        partners = self.env['res.partner'].browse(list(totals['partners'].keys()))
        errors = self._check_required_fields(partners, contact_person)
        self._raise_required_fields_errors(errors)

        edi_values = {
            'writer': self._get_writer_edi_data(),
            'debtor': self._get_debtor_edi_data(totals, dads_year),
            'receiver': DECLARATION_RECEIVER,
            'contact_person': {
                'name': contact_person.name,
                'email': contact_person.email,
                'phone': self._format_phone_number(contact_person.phone),
            },
            'beneficiaries': self._get_beneficiaries_edi_data(totals),
            'type': FUNCTIONAL_GROUP_TYPE,
            'declaration_type': DECLARATION_TYPE,
            'declaration_reference': DECLARATION_REFERENCE,
            'millesime': DECLARATION_MILLESIME,
            'is_test': '1' if is_test else '0',
        }

        edi_values = self._inject_insee_codes(edi_values)

        return edi_values
