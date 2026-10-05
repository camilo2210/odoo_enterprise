from lxml import etree
from stdnum.fr import siret

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import RedirectWarning, ValidationError
from odoo.tools import cleanup_xml_node

DECLARATION_WRITER_TYPE = 'CEC_EDI_TDFC'
DECLARATION_MILLESIME = '26'
FUNCTIONAL_GROUP_TYPE = 'INFENT'
DECLARATION_TYPE = 'IDF'
DECLARATION_REFERENCE = 'INFENT000000007'  # internal reference to the emitor

REPORTS_TO_EXPORT = {
    '2031': {
        'reports': ['l10n_fr_2031'],
        'handler': 'l10n_fr_reports.2031.report.handler',
        'post_added': [{'id': 'AH', 'value': 'OUI'}, {'id': 'AJ', 'ftx_1': 'Odoo'}],
    },
    '2031BIS': {
        'reports': ['l10n_fr_2031_annexes'],
        'handler': 'l10n_fr_reports.2031.annexes.report.handler',
    },
    '2033A': {
        'reports': ['l10n_fr_2033_A'],
        'handler': 'l10n_fr_reports.2033.a.report.handler',
        'nil_code': 'JD',
    },
    '2033B': {
        'reports': ['l10n_fr_2033_B'],
        'handler': 'l10n_fr_reports.2033.b.report.handler',
        'nil_code': 'JB',
    },
    '2033C': {
        'reports': ['l10n_fr_2033_C_1', 'l10n_fr_2033_C_2'],
        'handler': 'l10n_fr_reports.2033.c.report.handler',
        'nil_code': 'RQ',
    },
    '2033D': {
        'reports': ['l10n_fr_2033_D_1', 'l10n_fr_2033_D_2'],
        'handler': 'l10n_fr_reports.2033.d.report.handler',
        'nil_code': 'PF',
    },
    '2033E': {
        'reports': ['l10n_fr_2033_E'],
        'handler': 'l10n_fr_reports.2033.e.report.handler',
        'nil_code': 'DB',
    },
    '2033F': {
        'reports': ['l10n_fr_2033_F'],
        'handler': 'l10n_fr_reports.2033.f.report.handler',
        'nil_code': 'GS',
    },
    '2033G': {
        'reports': ['l10n_fr_2033_G'],
        'handler': 'l10n_fr_reports.2033.g.report.handler',
        'nil_code': 'GS',
    },
    '2065': {
        'reports': ['l10n_fr_2065_SD'],
        'handler': 'l10n_fr_reports.2065_sd.report.handler',
        'post_added': [{'id': 'AH', 'value': 'OUI'}, {'id': 'AJ', 'ftx_1': 'Odoo'}],
    },
    '2065BIS': {
        'reports': ['l10n_fr_2065_bis_SD'],
        'handler': 'l10n_fr_reports.2065_sd.bis.report.handler',
    },
    '2069RCI': {
        'reports': ['l10n_fr_2069_RCI', 'l10n_fr_2069_RCI_donations'],
        'handler': 'l10n_fr_reports.2069.rci.report.handler',
        'nil_code': 'AB',
        'repetition': '0001',
    },
}


class FiscalDeclarationHandler(models.AbstractModel):
    _name = 'l10n_fr_reports.fiscal_declaration_handler'
    _description = 'Fiscal Declaration Report Handler'
    _inherit = 'account.report.custom.handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report=report, options=options, previous_options=previous_options)
        if self.env.company.account_fiscal_country_id.code != 'FR':
            return

        options.setdefault('buttons', []).append({
            'name': self.env._("Download XML"),
            'action': 'action_download_fiscal_declaration',
        })
        options['buttons'].append({
            'name': self.env._("Import Datas"),
            'action': 'action_import_fiscal_declaration',
        })

    def _get_common_edi_vals(self, options, fiscal_declaration, date_from, date_to):
        sender_company = fiscal_declaration._get_sender_company_for_export(options)
        # Assume Emitor = Writer -> omit the emitor
        writer = sender_company.account_representative_id or sender_company
        tax_type = options.get('fiscal_declaration', {}).get('tax_type')
        special_circ = options.get('fiscal_declaration', {}).get('special_circ')
        rof_prefix = 'IS' if tax_type == 'IS' else 'BIC'
        debtor = sender_company
        writer_vals = {
            'siret': writer.l10n_fr_siret,
            'designation': DECLARATION_WRITER_TYPE,
            'designation_cont_1': writer.name[:35],
            'designation_cont_2': writer.name[35:70],
            'address': {
                'street': writer.street[:30],
                'complement': f"{writer.street[30:]} {writer.street2}"[:35],
                'postal_code': writer.zip[:17],
                'city': writer.city[:35],
                'country_code': writer.country_id.code,
            }
        }
        debtor_vals = {
            'identifier': debtor.l10n_fr_siren,
            'designation': debtor.name[:35],
            'address': {
                'street': debtor.street,
                'complement': debtor.street2,
                'postal_code': debtor.zip[:17],
                'city': debtor.city[:35],
                'country_code': debtor.country_id.code,
            },
            'rof': f'{rof_prefix}{sender_company.l10n_fr_rof_type}',
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
        # F-IDENTIF
        identif_vals = [
            {
                'id': 'AA',
                'identifier': debtor.l10n_fr_siren,
                'designation': debtor.display_name[:35],
                'address': {
                    'street': debtor.street,
                    'complement': debtor.street2,
                    'postal_code': debtor.zip[:17],
                    'city': debtor.city[:35],
                    'country_code': debtor.country_id.code,
                },
            },
            {'id': 'BA', 'value': 'BI' if tax_type == 'IS' else 'BC'},  # fiscal category (BI:BC)
            {'id': 'BB', 'value': 'RS'},  # simplified fiscal regime
            {'id': 'BC', 'value': tax_type},  # Tax Type (IR:IS)
            {'id': 'BD', 'value': special_circ if special_circ in {'CSS', 'DCD'} else ''},  # In case of cessation/deces (CSS:DCD)
            {'id': 'BF', 'value': 'DPR' if special_circ == 'DPR' else 'NOR'},  # Devinitive or provisional depot (DPR prov:NOR normal)
            {'id': 'CA', 'value': date_from},
            {'id': 'CB', 'value': date_to},
            {'id': 'DA', 'monnaie': sender_company.currency_id.name},
            {'id': 'KD', 'value': f'{rof_prefix}{sender_company.l10n_fr_rof_type}'},  # ROF
        ]
        return writer_vals, debtor_vals, edi_partner_vals, identif_vals

    def _prepare_tdfc_values(self, options, fiscal_declaration, date_from, date_to):
        """
        Prepares the values required to generate the fiscal declaration xml by collecting
        lines of each report needed

        :param options: dict - Report options dict
        :param fiscal_declaration: recordset - Fiscal declaration record
        :param date_from: str - Start date of reporting period
        :param date_to: str - End date of reporting period
        :return: Complete payload for xml construction
        :rtype: dict
        """
        forms_data = []
        errors_by_report = {}
        fiscal_declaration_options = options.get('fiscal_declaration')
        for report_name, config in REPORTS_TO_EXPORT.items():
            if fiscal_declaration_options and not fiscal_declaration_options.get(report_name):
                nil_code = config.get('nil_code')
                if not nil_code:
                    continue
                vals = [{'id': nil_code, 'value': 'X'}]
            else:
                lines = []
                for report in config['reports']:
                    section_id = self.env.ref(f'l10n_fr_reports.{report}').id
                    section = fiscal_declaration.section_report_ids.filtered(lambda sect: sect.id == section_id)
                    section_options = section.get_options({'date': options.get('date'), 'unfold_all': True})
                    lines.extend(section._get_lines(section_options))
                mapper = self.env[config['handler']]._get_code_to_edi_id()
                errors_by_report[report_name] = {}
                vals = self._export_report_data(lines, mapper, errors_by_report[report_name])

                if vals_to_add := config.get('post_added'):
                    # For some reports we need to set Odoo for computerized accounting field
                    vals.extend(vals_to_add)

            forms_data.append({
                'name': report_name,
                'zones': vals,
                'millesime': DECLARATION_MILLESIME,
                'repetition': config.get('repetition'),
            })

        errors_by_report = {report: report_errors for report, report_errors in errors_by_report.items() if report_errors.get('errors')}
        self._raise_many2one_errors(errors_by_report)

        writer_vals, debtor_vals, edi_partner_vals, identif_vals = self._get_common_edi_vals(options, fiscal_declaration, date_from, date_to)
        return {
            'date_from': date_from,
            'date_to': date_to,
            'is_test': '1' if self.env['account.report.async.document']._is_aspone_test_mode() else '0',
            'type': FUNCTIONAL_GROUP_TYPE,
            'declarations': [{
                'type': DECLARATION_TYPE,
                'reference': DECLARATION_REFERENCE,
                'writer': writer_vals,
                'debtor': debtor_vals,
                'edi_partner': edi_partner_vals,
                'recipients': [{'designation': "DGI_EDI_TDFC"}],
                # F-IDENTIF form
                'identif': {
                    'millesime': DECLARATION_MILLESIME,
                    'zones': identif_vals,
                },
                'forms': forms_data,
            }],
        }

    def _extract_model_and_id(self, value):
        """
        Handler to split columns values where the 'figure_type' is set to 'many2one'
        as the value will be in in 'model:res_id' format

        :param str: value - string to parse formatted as 'model_name:id'
        :return: A tuple of (model_name, integer_id),
                (None, None) if the format is invalid or (model_name, None) if the ID
                is not numeric.
        :rtype: tuple
        """
        if not value or ':' not in value:
            return None, None

        res_model, res_id = value.split(':', 1)
        if res_id.isdecimal():
            return res_model, int(res_id)
        return res_model, None

    def _collect_return_required_data(self, options, fiscal_declaration):
        """
        Collects the necessary informations required to construct the account returns

        :param options: dict - Report options dict
        :param fiscal_declaration: recordset - Fiscal declaration record
        :return: In reports datas that need to be analyzed
        :rtype: dict
        """
        fiscal_declaration_options = options.get('fiscal_declaration')

        collected_data = {
            'partners_mandatory_fields': {},
        }
        for report_name, config in REPORTS_TO_EXPORT.items():
            if fiscal_declaration_options and not fiscal_declaration_options.get(report_name):
                continue

            lines = []
            mapper = self.env[config['handler']]._get_code_to_edi_id()
            for report in config['reports']:
                section_id = self.env.ref(f'l10n_fr_reports.{report}').id
                section = fiscal_declaration.section_report_ids.filtered(lambda sect: sect.id == section_id)
                section_options = section.get_options({'date': options.get('date'), 'unfold_all': True})
                lines.extend(section._get_lines(section_options))

            for line in lines:
                if not line.code:
                    continue
                splitted_code = line.code.rsplit('_', 2)
                line_code = splitted_code[0] if splitted_code[-1] == 'dynadded' else line.code

                for column in line.columns:
                    if column.figure_type == 'many2one' and column.no_format:
                        # collects all linked partners with their mandatory fields
                        res_model, res_id = self._extract_model_and_id(column.no_format)
                        if res_model == 'res.partner' and res_id:
                            zone_details = mapper.get(line_code, {}).get(column.expression_label, {})
                            mandatory = zone_details.get('structure', {}).get('mandatory', set())
                            if mandatory:
                                collected_data['partners_mandatory_fields'].setdefault(res_id, set()).update(mandatory)
        return collected_data

    def _raise_many2one_errors(self, errors_by_report):
        if not errors_by_report:
            return
        error_list = []
        all_invalid_partners = self.env['res.partner']
        missing_fields_per_partner = {}

        for report_name, report_errors in errors_by_report.items():
            errors = report_errors['errors']
            error_list.append(self.env._("\nForm %(form)s:", form=report_name))
            error_list.extend(f" - {err}" for err in errors)
            all_invalid_partners |= report_errors['records']

            for res_id, missing_fields in (report_errors.get('missing_fields_per_partner') or {}).items():
                missing_fields_per_partner.setdefault(res_id, []).extend(list(missing_fields))

        view_list = self.env.ref('l10n_fr_reports.view_partner_das2_required_partner_fields')
        view_form = self.env.ref('l10n_fr_reports.view_partner_form_inherit_das2_required_partner_fields')
        action = all_invalid_partners._get_records_action(
            name=self.env._("Missing partner data"),
            views=[(view_list.id, 'list'), (view_form.id, 'form')],
            domain=[('id', 'in', all_invalid_partners.ids)],
        )

        raise RedirectWarning(
            self.env._("Fiscal Declaration cannot be generated due to missing fields on linked partners: \n%(missing_fields)s", missing_fields="\n".join(error_list)),
            action,
            self.env._("Update partners"),
        )

    def _raise_debtor_writer_redirect(self, entity, errors):
        raise RedirectWarning(
            self.env._(
                "Fiscal Declaration cannot be generated: \n\n"
                "[%(missing_fields)s] fields are missing or are misconfigured",
                missing_fields=", ".join([err[0] for err in errors])
            ),
            entity._get_records_action(),
            self.env._("Update %(model)s", model=entity.display_name),
        )

    def _check_values_export(self, options, fiscal_declaration):
        debtor = fiscal_declaration._get_sender_company_for_export(options)
        if debtor_errors := self._get_entity_missing_fields(debtor, {'identifier'}):
            self._raise_debtor_writer_redirect(debtor, debtor_errors)

        if (writer := debtor.account_representative_id) and (writer_errors := self._get_entity_missing_fields(writer, {'identifier'})):
            self._raise_debtor_writer_redirect(writer, writer_errors)

    def _get_entity_missing_fields(self, entity, mandatory_fields=None):
        checks = [
            (not entity.street, self.env._("street"), 'street'),
            (not entity.zip, self.env._("postal code"), 'zip'),
            (not entity.city, self.env._("city"), 'city'),
            (not entity.country_id, self.env._("country"), 'country_id'),
        ]
        if mandatory_fields and 'identifier' in mandatory_fields:
            is_invalid_siret = not entity.l10n_fr_siret or not siret.is_valid(entity.l10n_fr_siret)
            checks.append((is_invalid_siret, self.env._("company ID"), 'identifier'))
        if mandatory_fields and 'profession' in mandatory_fields:
            checks.append((not entity.l10n_fr_profession_id, self.env._("profession"), 'profession'))

        return [(msg, field) for condition, msg, field in checks if condition]

    @api.model
    def _check_required_fields(self, options):
        """
        Validates the mandatory fields required to construct account returns

        :param options: dict - Report options dict
        :return: Errors and corresponding records
        :rtype: dict
        """
        fiscal_declaration = self.env['account.report'].browse(options['sections_source_id'])
        debtor = fiscal_declaration._get_sender_company_for_export(options)
        writer = debtor.account_representative_id

        debtor_errors = self._get_entity_missing_fields(debtor, {'identifier'})
        writer_errors = self._get_entity_missing_fields(writer, {'identifier'}) if writer else []

        collected_data = self._collect_return_required_data(options, fiscal_declaration)

        partners_mandatory_fields = collected_data['partners_mandatory_fields']
        invalid_partners = self.env['res.partner']
        missing_fields_map = {}
        if partners_mandatory_fields:
            partners = self.env['res.partner'].browse(list(partners_mandatory_fields.keys()))
            for partner in partners:
                if errors := self._get_entity_missing_fields(partner, partners_mandatory_fields.get(partner.id) or set()):
                    missing_fields_map.setdefault(partner.id, []).extend(err[1] for err in errors)
                    invalid_partners |= partner

        return {
            'partners': {
                'errors': missing_fields_map,
                'records': invalid_partners,
            },
            'writer': {
                'errors': writer_errors,
                'record': writer,
            },
            'debtor': {
                'errors': debtor_errors,
                'record': debtor,
            },
        }

    @api.model
    def _export_fiscal_declaration(self, options):
        """
        Generates and exports the fiscal declaration as an XML file
        Entry point for the fiscal declaration export

        :param dict options: dict - Report options dict
        :return: Generated 'file_name' and the raw 'file_content' (XML)
        :rtype: dict
        """
        date_to = fields.Date.to_date(options['date']['date_to'])
        date_from = date_to - relativedelta(years=1)
        fiscal_declaration = self.env['account.report'].browse(options['sections_source_id'])
        self._check_values_export(options, fiscal_declaration)

        vals = self._prepare_tdfc_values(options, fiscal_declaration, date_from.strftime('%Y%m%d'), date_to.strftime('%Y%m%d'))
        xml_content = self.env['ir.qweb']._render('l10n_fr_reports.aspone_xml_edi', vals)
        try:
            xml_content.encode('ISO-8859-15')
        except UnicodeEncodeError as e:
            raise ValidationError(
                self.env._("The xml file generated contains an invalid character: '%s'", xml_content[e.start:e.end]))
        xml_content = etree.tostring(cleanup_xml_node(xml_content), encoding='ISO-8859-15', standalone='yes')

        return {
            'file_name': f"{self.env._("Fiscal_Declaration")}_{self.env.company.name}_{date_to.year}.xml",
            'file_content': xml_content,
        }

    def _get_record(self, value):
        res_model, res_id = self._extract_model_and_id(value)
        if res_model and res_id:
            record = self.env[res_model].browse(res_id)
            return record if record.exists() else None
        return None

    def _group_lines_by_parent(self, lines):
        grouped_lines = {}
        for line in lines:
            if line.parent_id is None:
                continue
            grouped_lines.setdefault(line.parent_id, []).append(line)
        return grouped_lines

    def format_value(self, value, field_type, value_format=None):
        """
        Formats a raw value according to specific EDI rules

        :param value: mixed - Column raw value to be formatted
        :param field_type: str - Data type of the value
        :param value_format: str - Optional EDI format code
        :return: Formatted value
        :rtype: mixed (str, int, float)
        """
        if value_format == 'TBX':
            value = 'X' if value else ''

        elif value_format == '102' or value_format == '602' or field_type == 'date':
            if not value:
                return ''
            try:
                date_value = fields.Date.to_date(value)
                value = date_value.strftime('%Y') if value_format == '602' else date_value.strftime('%Y%m%d')
            except (ValueError, TypeError):
                value = ''

        elif value_format == 'TON':
            value = 'OUI' if value else 'NON'

        elif value_format == 'TST':
            value = 'I' if value else 'S'

        elif value:
            if field_type == 'integer':
                value = int(round(value, 0))

            elif field_type == 'monetary':
                value = round(value, 0)

            elif field_type == 'percentage':
                value = round(value, 2)

        return value

    def _build_simple_node(self, value, figure_type, zone_details, partners_errors=None):
        """
        Builds EDI node dict from a value of a single line, if this value is in a many2one format
        it will be processed to build a more complex node and save the partners missing fields

        :param value: mixed - Column raw value to be formatted
        :param figure_type: str - Data type of the value
        :param zone_details: dict - Schema of the configuration for this specific EDI zone
        :param partners_errors: dict - To collect missing field for partners
        :return: Value(s) to build the zone
        :rtype: dict
        """
        tag = zone_details.get('tag', 'value')
        structure = zone_details.get('structure')
        value_format = zone_details.get('format')

        if figure_type == 'many2one':
            record = self._get_record(value)
            if record and record._name == 'res.partner' and partners_errors is not None:
                if missing_fields := self._get_entity_missing_fields(record, structure.get('mandatory') or set()):
                    partners_errors.setdefault('missing_fields_per_partner', {})[record.id] = [err[1] for err in missing_fields]
                    partners_errors.setdefault('errors', []).append(self.env._("%(missing_fields)s are not set on %(partner)s", missing_fields=[field[0] for field in missing_fields], partner=record.name))
                    partners_errors['records'] = partners_errors.get('records', self.env['res.partner']) | record

                return self._build_address_node(record, structure)

        return {tag: self.format_value(value, figure_type, value_format)}

    def _build_nested_node(self, lines, dependencies, expression_label, is_dynadded):
        """
        Builds EDI node dict from the values of multiple children lines

        :param lines: list - Needed lines to construct the node
        :param dependencies: dict - Schema mapping report line codes to their dict paths
        :param expression_label: str - Column label to extract the value from
        :param is_dynadded: bool - Indicates if the lines wre dynamically added
        :return: Values to build the zone
        :rtype: dict
        """
        def get_column(line, expression_label):
            return next((col for col in line.columns if col.expression_label == expression_label), None)

        node = {}
        for line in lines:
            if not line.code:
                continue
            if path := dependencies.get(line.code.rsplit('_', 2)[0] if is_dynadded else line.code):
                column = get_column(line, expression_label)
                if not column:
                    continue
                if column.figure_type == 'many2one':
                    record = self._get_record(column.no_format)
                    value = record.code if record and record._name == 'res.country' else None
                else:
                    value = self.format_value(column.no_format, column.figure_type)

                node_level = node
                for key in path[:-1]:
                    node_level.setdefault(key, {})
                    node_level = node_level[key]
                node_level[path[-1]] = value
        return node

    def _build_address_node(self, record, structure):
        def get_field_value(record, key):
            field = structure.get(key)
            if not field:
                return False
            values = record.mapped(field)
            return values[0] if values else False

        id_number = False
        if identifier := structure.get('identifier'):
            id_number = get_field_value(record, identifier['number'])
            if id_number and identifier.get('is_siren'):
                id_number = id_number[:9]

        return {
            'identifier': id_number,
            'designation': get_field_value(record, 'designation'),
            'designation_1': get_field_value(record, 'designation_1'),
            'designation_2': get_field_value(record, 'designation_2'),
            'address': {
                'number': get_field_value(record, 'number'),
                'street': get_field_value(record, 'street'),
                'complement': get_field_value(record, 'complement'),
                'hamlet': get_field_value(record, 'hamlet'),
                'postal_code': get_field_value(record, 'postal_code'),
                'city': get_field_value(record, 'city'),
                'country_code': get_field_value(record, 'country_code'),
            },
            'telephone': get_field_value(record, 'telephone'),
            'email': get_field_value(record, 'email'),
        }

    def _export_report_data(self, lines, schema, report_partners_errors=None):
        """
        Iterates through the report lines to extract their values and create the corresponding EDI zones

        :param lines: list - Report lines (AccountReportAccountReportLineData dataclass) to parse
        :param schema: dict - Mapping schema linking report line codes to EDI corresponding tag
        :param report_partners_errors: dict - To collect errors related to 'many2one' expressions
        :return: Dicts representing the EDI zones ready for XML generation
        :rtype: list
        """
        def set_value(node, to_add, is_repeatable):
            if not to_add:
                return
            if is_repeatable:
                dest = node.setdefault('occurences', [])
                number = str(len(dest) + 1).zfill(4)
                to_add.update({'occurence_number': number})
                dest.append(to_add)
            else:
                node.update(to_add)

        data = {}
        lines_by_parent = self._group_lines_by_parent(lines)
        for line in lines:
            if not line.code:
                continue

            needed_line_code = schema.get(line.code)
            if not needed_line_code:
                # if not found, verify if it is not a dynamically added one
                # dynamically added line code structure: {default_code}_{uuid}_dynadded
                splitted_code = line.code.rsplit('_', 2)
                if splitted_code[-1] == 'dynadded':
                    needed_line_code = schema.get(splitted_code[0])
            if not needed_line_code:
                continue

            for column in line.columns:
                if zone_details := needed_line_code.get(column.expression_label):
                    zone_id = zone_details['zone']
                    node = data.setdefault(zone_id, {'id': zone_id})
                    is_repeatable = zone_details.get('repeatable')
                    if node_schema := zone_details.get('depends'):
                        # some zone needs values from muliple lines to be build (e.g. addresses)
                        to_add = self._build_nested_node(lines_by_parent[line.id], node_schema, column.expression_label, line.code.endswith('dynadded'))
                    else:
                        to_add = self._build_simple_node(column.no_format, column.figure_type, zone_details, report_partners_errors)

                    if pair := zone_details.get('pairs_with'):
                        # some datas are send with 2 zones, one containing the label as a value and other the actual value as a value
                        set_value(data.setdefault(pair[0], {'id': pair[0]}), {'value': pair[1]}, is_repeatable)

                    set_value(node, to_add, is_repeatable)

        return list(data.values())

    def action_download_fiscal_declaration(self, options):
        xml = self._export_fiscal_declaration(options)

        attachment = self.env['ir.attachment'].create({
            'name': xml['file_name'],
            'type': 'binary',
            'raw': xml['file_content'],
            'mimetype': 'application/zip'
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'download',
        }

    @api.model
    def action_import_fiscal_declaration(self, options):
        wizard = self.env['l10n_fr.import.fiscal.declaration'].create({
            'report_id': options.get('report_id'),
        })
        return wizard._get_records_action(name=self.env._("Import Fiscal Declaration"), target="new")
