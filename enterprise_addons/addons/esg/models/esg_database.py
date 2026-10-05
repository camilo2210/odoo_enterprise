import calendar
import contextlib
import datetime
import json
import logging
import math
import re
import requests
import unicodedata

from io import BytesIO
from lxml import html
from requests.exceptions import HTTPError, RequestException

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import format_date
from odoo.tools.float_utils import float_compare

_logger = logging.getLogger(__name__)


class EsgDatabase(models.Model):
    _name = 'esg.database'
    _description = 'Database'

    name = fields.Char(required=True)
    url = fields.Char()
    image = fields.Binary()
    last_update = fields.Date()
    latest_version = fields.Date()
    color = fields.Integer(compute='_compute_kanban_display')
    kanban_text = fields.Char(compute='_compute_kanban_display')
    can_be_downloaded = fields.Boolean(compute='_compute_can_be_downloaded')

    @api.depends('latest_version', 'last_update')
    def _compute_kanban_display(self):
        for db in self:
            db.color = False
            db.kanban_text = self.env._("Not loaded")
            if not db.last_update:
                continue
            formatted_date = format_date(self.env, db.last_update, date_format='MMMM y')
            db.kanban_text = self.env._("Updated on: %(date)s", date=formatted_date)
            if db.last_update >= db.latest_version:
                db.color = 7
            else:
                db.color = 2

    def _compute_can_be_downloaded(self):
        ademe_db = self.env.ref('esg.esg_database_ademe')
        ipcc_db = self.env.ref('esg.esg_database_ipcc')
        for database in self:
            if database in (ademe_db, ipcc_db):
                database.can_be_downloaded = True
            else:
                database.can_be_downloaded = False

    @api.ondelete(at_uninstall=False)
    def _prevent_database_deletion(self):
        ademe_db = self.env.ref('esg.esg_database_ademe')
        ipcc_db = self.env.ref('esg.esg_database_ipcc')
        if ademe_db in self:
            raise ValidationError(self.env._("You can't delete the ADEME database."))
        if ipcc_db in self:
            raise ValidationError(self.env._("You can't delete the IPCC database."))

    def action_load_data(self):
        self.ensure_one()
        if self == self.env.ref('esg.esg_database_ademe'):
            result = self._action_import_ademe_file()
        elif self == self.env.ref('esg.esg_database_ipcc'):
            result = self._action_import_efdb_from_ipcc()
        else:
            raise ValidationError(self.env._("Database file is missing"))
        if result is True:
            self.last_update = self.latest_version
        action_view_emission_factor = self.env['ir.actions.actions']._for_xml_id('esg.action_view_emission_factor')
        action_view_emission_factor['domain'] = [('database_id', '=', self.id)]
        return action_view_emission_factor

    def action_unload_data(self):
        self.ensure_one()
        if not self.last_update:
            raise UserError(self.env._('You cannot remove a database that was not loaded.'))
        factors_to_remove = self.env['esg.emission.factor'].search([('database_id', '=', self.id)])
        source_ids_to_remove = factors_to_remove.source_id.ids
        factors_to_remove.unlink()
        self.env['esg.emission.source'].browse(source_ids_to_remove).unlink()
        self.last_update = False
        self.latest_version = False

    def _external_api_call(self, request_url):
        ademe_api_url = 'https://data.ademe.fr/data-fair/api/v1/datasets/base-carboner'
        if not request_url.startswith(ademe_api_url):
            raise ValidationError(self.env._('Invalid URL.'))
        response_error = {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                },
            }
        try:
            request_response = requests.request(
                'GET',
                request_url,
                timeout=(30, 30),
            )
            request_response.raise_for_status()
        except (ValueError, HTTPError, RequestException) as exception:
            response_error['params']['message'] = self.env._(
                "Server returned an unexpected error: %(error)s",
                error=(request_response.text or str(exception)),
            )
            return response_error

        try:
            response_text = request_response.text
            response_data = json.loads(response_text)
        except json.JSONDecodeError:
            response_error['params']['message'] = self.env._("JSON response could not be decoded.")
            return response_error

        return response_data

    # =============
    # ADEME IMPORT
    # =============
    def _get_ademe_emission_factor_values(self, lines):
        MONTHS_FR = {
            'janv': 1, 'janvier': 1,
            'févr': 2, 'fevr': 2, 'février': 2, 'fevrier': 2,
            'mars': 3,
            'avr': 4, 'avril': 4,
            'mai': 5,
            'juin': 6,
            'juil': 7, 'juillet': 7,
            'août': 8, 'aout': 8,
            'sept': 9, 'septembre': 9,
            'oct': 10, 'octobre': 10,
            'nov': 11, 'novembre': 11,
            'déc': 12, 'dec': 12, 'décembre': 12, 'decembre': 12
        }

        REGION_TO_NAME = {
            'alsace':                     'Alsace',
            'aquitaine':                  'Aquitaine',
            'auvergne':                   'Auvergne',
            'basse normandie':            'Basse-Normandie',
            'bourgogne':                  'Bourgogne',
            'bretagne':                   'Bretagne',
            'centre':                     'Centre',
            'centre val de loire':        'Centre',                       # variant -> Centre
            'champagne ardenne':          'Champagne-Ardenne',
            'corse':                      'Corse',
            'corsica':                    'Corse',                        # EN spelling
            'franche comte':              'Franche-Comté',
            'haute normandie':            'Haute-Normandie',
            'ile de france':              'Île-de-France',                # covers Ile- and Île-
            'languedoc roussillon':       'Languedoc-Roussillon',
            'limousin':                   'Limousin',
            'lorraine':                   'Lorraine',
            'midi pyrenees':              'Midi-Pyrénées',                # covers Pyrenées/Pyrénées
            'nord pas de calais':         'Nord-Pas-de-Calais',           # covers -De-/-de-
            'pays de la loire':           'Pays de la Loire',             # covers hyphenated form
            'picardie':                   'Picardie',
            'poitou charente':            'Poitou-Charentes',             # singular -> plural
            'poitou charentes':           'Poitou-Charentes',
            'provence alpes cote d azur': 'Provence-Alpes-Côte d\'Azur',
            'rhone alpes':                'Rhône-Alpes',
            # overseas regions
            'guadeloupe':                 'Guadeloupe',
            'martinique':                 'Martinique',
            'guyane':                     'Guyane',
            'french guyana':              'Guyane',
            'reunion':                    'La Réunion',
            'reunion island':             'La Réunion',
            'la reunion':                 'La Réunion',
            'mayotte':                    'Mayotte',
        }

        COUNTRY_NAME_MAP = {
            "Chinese Taipei": "Taiwan",
            "Congo": "Congo (Republic)",
            "Dem. Rep. of Congo": "Congo (DRC)",
            "DPR of Korea (north)": "North Korea",
            "FYR of Macedonia": "North Macedonia",
            "Irland": "Ireland",
            "Italia": "Italy",
            "Netherland": "Netherlands",
            "Republic of Moldova": "Moldova",
            "Slovak Republic": "Slovakia",
            "Syrian Arab Republic": "Syria",
            "Turkey": "Türkiye",
            "United Rep. of Tanzania": "Tanzania",
        }

        def norm(s):
            """Lowercase, strip accents, flatten hyphens/apostrophes/spaces."""
            s = s.strip().lower()
            s = ''.join(c for c in unicodedata.normalize('NFD', s)
                        if unicodedata.category(c) != 'Mn')
            for ch in "-'’/":
                s = s.replace(ch, ' ')
            return ' '.join(s.split())

        def map_to_region(value):
            """Return the canonical old region NAME, or None if unmappable."""
            return REGION_TO_NAME.get(norm(value.split(',', 1)[0]))

        def map_to_country(value):
            return COUNTRY_NAME_MAP.get(value, value)

        def parse_ademe_date(date_str):
            date_str = date_str.strip().lower()

            # Deals with years given in 2 digits (eg: "18" -> 2018)
            def get_year(y_str):
                y = int(y_str)
                return y + 2000 if y < 100 else y

            # 1. Fixed format with slash : "31/12/2023"
            match = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', date_str)
            if match:
                d, m, y = map(int, match.groups())
                return datetime.datetime(y, m, d)

            # 2. Textual fixed format : "31-mars-21" or "29-déc-23"
            match = re.match(r'^(\d{1,2})-([a-zûéè]+)-(\d{2,4})$', date_str)
            if match:
                d_str, m_str, y_str = match.groups()
                m = MONTHS_FR.get(m_str)
                if m:
                    y = get_year(y_str)
                    return datetime.datetime(y, m, int(d_str))

            # 3. Format month-year : "déc-18" or "janv-25" → last day of the month
            match = re.match(r'^([a-zûéè]+)-(\d{2,4})$', date_str)
            if match:
                m_str, y_str = match.groups()
                m = MONTHS_FR.get(m_str)
                if m:
                    y = get_year(y_str)
                    last_day = calendar.monthrange(y, m)[1]
                    return datetime.datetime(y, m, last_day)

            # 4. Format complete year : "Année 2008" or "2026" → 31 December
            match = re.match(r'^(?:année\s+)?(\d{4})$', date_str)
            if match:
                y = int(match.group(1))
                return datetime.datetime(y, 12, 31)

            return False

        existing_factors = dict(self.env['esg.emission.factor']._read_group(
            domain=[('database_id', '=', self.id)],
            groupby=['code'],
            aggregates=['id:recordset'],
        ))
        gasses = {
            'CO2f': self.env.ref('esg.esg_gas_co2'),
            'CH4f': self.env.ref('esg.esg_gas_ch4f'),
            'CH4b': self.env.ref('esg.esg_gas_ch4b'),
            'N2O': self.env.ref('esg.esg_gas_n2o'),
            'SF6': self.env.ref('esg.esg_gas_sf6'),
        }
        hardcoded_units_conversion = {
            'kg of active substance': 'kg', 'kg (live weight)': 'kg', 'kg net weight': 'kg',
            'kg of spreaded nitrogen': 'kg', 'kg of suppressed DCO': 'kg', 'kg of treated leather': 'kg',
            'Kg': 'kg', 'kg of spreaded nitrgen': 'kg', 'kgH2': 'kg', 'kg NTK': 'kg', 'kg BioGNC': 'kg',
            'liter': 'L', 'Liter': 'L',
            'ton': 't', 'ton of K2O': 't', 'ton of N': 't', 'ton of P2O5': 't',
            'ton of clinker': 't', 'ton of waste': 't', 'tonne': 't',
            'unit': 'Units', 'meal': 'Units', 'device': 'Units', 'plant': 'Units',
            'm of road': 'm',
            'm²  net floor area': 'm²', 'm² of ceiling': 'm²', 'm² of floor': 'm²',
            'm² of wall': 'm²', 'm2 SHON': 'm²',
            'm3': 'm³', 'm3 (n)': 'm³',
            'mL': 'ml',
            'hour': 'Hours', 'heure': 'Hours',
            'kWh (LHV)': 'KWH', 'kWh (PCI)': 'KWH', 'kWh HHV': 'KWH', 'kWh ICV': 'KWH', 'kWhPCI': 'KWH',
            'kWh IVC': 'KWH', 'kWh LHV': 'KWH', 'kWh SCV': 'KWH', 'KWh ICV': 'KWH', 'KWH': 'KWH', 'kWh': 'KWH',
            'GJ ICV': 'GJ', 'MJ ICV': 'MJ', 'GJ PCI': 'GJ', 'GJ SCV': 'GJ', 'GJ IVC': 'GJ',
            'toe ICV': 'toe', 'toe SCV': 'toe', 'tep PCI': 'toe', 'tep IVC': 'toe', 'TOe ICV': 'toe',
        }
        unknown_units = {
            '100 A4 sheets', 't.km', 'ton.km', 'm3.km', 'passager.km', 'passenger.km', 'ha.year', 'person.month', 'kgH2/100km',
        }
        hardcoded_source_scopes = {
            'Achats de biens': 'indirect_others',
            'Process et émissions fugitives': 'direct',
            'Achats de services': 'indirect_others',
            'Combustibles': 'direct',
            'Transport de marchandises': 'indirect_others',
            'Transport de personnes': 'indirect_others',
            'Statistiques territoriales': 'direct',
            'UTCF': 'direct',
            'Traitement des déchets': 'indirect_others',
            'Electricité': 'indirect',
            'Réseaux de chaleur / froid': 'direct',
        }

        def _get_gas_lines(line, gasses, total_emissions):
            gas_lines = []
            for gas in ['CO2f', 'CH4f', 'CH4b', 'N2O']:
                if line.get(gas, 0) > 0:
                    gas_lines.append({
                        'gas_id': gasses[gas],
                        'quantity': line[gas],
                        'activity_type_id': line.get('Type_poste', False),
                    })
            for i in range(1, 6):
                additional_gas = line.get(f"Code_gaz_supplémentaire_{i}", None)
                if additional_gas and additional_gas in ['SF6']:
                    gas_lines.append({
                        'gas_id': gasses[additional_gas],
                        'quantity': line.get(f"Valeur_gaz_supplémentaire_{i}", 0),
                        'activity_type_id': line.get('Type_poste', False),
                    })
            # if the gaz decomposition is equal to the total emissions, that means that the decomposition
            # is given with CO2 equivalent value; each line needs to be adapted to have the gaz volume instead
            if not float_compare(sum(gas['quantity'] for gas in gas_lines), total_emissions, precision_rounding=0.1):
                for gas in gas_lines:
                    gas['quantity'] = gas['quantity'] / gas['gas_id'].global_warming_potential

            return gas_lines

        _logger.info("ESG: Processing raw lines")
        line_values = []
        posts_gas_lines = []
        # Used for the country/states mapping
        country_names_to_fetch = set()
        state_names_to_fetch = set()
        needs_france = False
        needs_europe = False
        skipped_line_codes = []

        for raw_line in lines:
            if not raw_line:
                continue
            line = raw_line  # dict(zip(dict_keys, raw_line))
            if line["Statut_de_l'élément"] == "Archivé" or\
                line["Type_de_l'élément"] == "Données source":
                continue

            total_emissions = line['Total_poste_non_décomposé']
            if line["Type_Ligne"] == "Poste":
                posts_gas_lines += _get_gas_lines(line, gasses, total_emissions)
                line_values[-1]['gas_line_ids'] = posts_gas_lines
                continue

            from_date = datetime.datetime.strptime(line.get('Date_de_création', ''), '%Y-%m-%d')
            to_date = parse_ademe_date(line.get('Période_de_validité', ''))
            if from_date and to_date and to_date < from_date:
                from_date = to_date
                to_date = False

            posts_gas_lines = []
            gas_lines = _get_gas_lines(line, gasses, total_emissions)

            normalized_unit = line.get('Unité_anglais', line.get('Unité_français', '')).replace('kgCO2e/', '')
            normalized_unit = hardcoded_units_conversion.get(normalized_unit, normalized_unit)
            if normalized_unit in unknown_units:
                skipped_line_codes.append(line["Identifiant_de_l'élément"])
                continue

            loc = line.get("Localisation_géographique")
            sub_loc = line.get("Sous-localisation_géographique_anglais")

            if loc in ["France continentale", "Outre-mer"]:
                needs_france = True
                if sub_loc:
                    if cleaned_state := map_to_region(sub_loc):
                        state_names_to_fetch.add(cleaned_state)
                    else:
                        skipped_line_codes.append(line["Identifiant_de_l'élément"])
                        continue
            elif loc == "Autre pays du monde":
                if sub_loc:
                    country_names_to_fetch.add(map_to_country(sub_loc))
            elif loc == "Europe":
                needs_europe = True

            factor_values = {
                'name': f'{line.get("Nom_base_anglais", "")} {line.get("Nom_attribut_anglais", "")} {line.get("Nom_frontière_anglais", "")}'
                    if line.get("Nom_base_anglais", '')
                    else f'{line.get("Nom_base_français", "")} {line.get("Nom_attribut_français", "")} {line.get("Nom_frontière_français", "")}',
                'code': line["Identifiant_de_l'élément"],
                'database_id': self.id,
                'uom_id': normalized_unit,
                'esg_uncertainty_value': line.get('Incertitude', 0) / 100,
                'compute_method': 'physically',
                'valid_from': from_date,
                'valid_to': to_date,
                'source_id': line['Code_de_la_catégorie'],
                'gas_line_ids': gas_lines,
                'loc': loc,
                'sub_loc': sub_loc,
            }
            if not gas_lines:
                factor_values['esg_emissions_value'] = total_emissions
            line_values.append(factor_values)
        _logger.info("ESG: Records skipped due to unknown location: %s", skipped_line_codes)

        _logger.info("ESG: Checking existing units, emission sources and esg activity type")
        # Prepare to process all units at once to avoid multiplying queries and loops
        units = [line['uom_id'].strip() for line in line_values]
        existing_units = dict(
            self.env['uom.uom']._read_group(
                domain=[('name', 'in', units)],
                groupby=['name'],
                aggregates=['id:recordset'],
            )
        )
        # Prepare to process all sources at once to avoid multiplying queries and loops
        source_tree_list = []
        for line in line_values:
            source_tree_list.append([s.strip() for s in line['source_id'].split('>')])
        all_sources_name = {item for sublist in source_tree_list for item in sublist}
        existing_sources = {(name, parent): record for name, parent, record in self.env['esg.emission.source']._read_group(
            domain=[('name', 'in', all_sources_name)],
            groupby=['name', 'parent_id'],
            aggregates=['id:recordset'],
        )}

        # Prepare to process all activity types at once to avoid multiplying queries and loops
        existing_activity_types = dict(
            self.env['esg.activity.type']._read_group(
                domain=[],
                groupby=['name'],
                aggregates=['id:recordset'],
            )
        )

        _logger.info("ESG: Processing link to related records")
        eur_currencies_pattern = re.compile(r'^keuro( \(\d{4}\) HT)?$')
        eur_currencies = {'euro spent'}
        # slow loop, should be optimized
        for source_tree, unit, line in zip(source_tree_list, units, line_values):
            # units
            existing_unit = existing_units.get(unit, False)
            if not existing_unit and not bool(eur_currencies_pattern.match(unit)) and not unit in eur_currencies:
                existing_unit = self.env['uom.uom'].create({'name': unit})
                existing_units[unit] = existing_unit
            if bool(eur_currencies_pattern.match(unit)) or unit in eur_currencies:
                currency_eur = self.env.ref('base.EUR')
                line['currency_id'] = currency_eur.id
                line['uom_id'] = False
                line['compute_method'] = 'monetary'
                if unit != 'euro spent':
                    line['esg_emissions_value'] = line['esg_emissions_value'] / 1000
            else:
                line['uom_id'] = existing_unit.id
            # sources
            previous_existing_source = self.env['esg.emission.source']
            for source_name in source_tree:
                existing_source = existing_sources.get((source_name, previous_existing_source), False)
                if not existing_source:
                    existing_source = self.env['esg.emission.source'].create({
                        'name': source_name,
                        'parent_id': previous_existing_source.id,
                        'scope': hardcoded_source_scopes.get(source_name, previous_existing_source.scope) or 'direct',
                    })
                    existing_sources[source_name, previous_existing_source] = existing_source
                previous_existing_source = existing_source
            line['source_id'] = previous_existing_source.id
            # activity types + declare gas lines correctly
            if line['gas_line_ids']:
                for gas_line in line['gas_line_ids']:
                    gas_line['gas_id'] = gas_line['gas_id'].id
                    if not gas_line['activity_type_id']:
                        continue
                    activity = existing_activity_types.get(gas_line['activity_type_id'], False)
                    if not activity:
                        activity = self.env['esg.activity.type'].create({'name': gas_line['activity_type_id']})
                        existing_activity_types[gas_line['activity_type_id']] = activity
                    gas_line['activity_type_id'] = activity.id
                line['gas_line_ids'] = [Command.create(gas) for gas in line['gas_line_ids']]

        # Countries and states fetching
        _logger.info("ESG: Fetching countries and states")
        if needs_france:
            country_names_to_fetch.add("France")
        country_name_to_id = {}
        if country_names_to_fetch:
            countries = self.env['res.country'].search([('name', 'in', list(country_names_to_fetch))])
            country_name_to_id = {c.name.lower(): c.id for c in countries}

        state_name_to_id = {}
        if state_names_to_fetch:
            state_domain = [('name', 'in', list(state_names_to_fetch))]
            states = self.env['res.country.state'].search(state_domain)
            state_name_to_id = {s.name.lower(): s.id for s in states}

        europe_country_ids = []
        if needs_europe:
            europe_group = self.env.ref('base.europe_prefix', raise_if_not_found=False)
            if europe_group:
                europe_country_ids = europe_group.country_ids.ids

        # Final iteration on the resulting factors
        new_factor_values = []
        write_factor_values = {}
        for line_value in line_values:
            # Apply the mapping on fetched res.country and res.country.state records
            loc = line_value.pop("loc")
            sub_loc = line_value.pop("sub_loc")
            c_ids = []
            s_ids = []

            if loc in ["France continentale", "Outre-mer"]:
                if "france" in country_name_to_id:
                    c_ids.append(country_name_to_id["france"])
                if sub_loc:
                    cleaned_state = map_to_region(sub_loc)
                    if cleaned_state and cleaned_state.lower() in state_name_to_id:
                        s_ids.append(state_name_to_id[cleaned_state.lower()])
            elif loc == "Autre pays du monde":
                if sub_loc:
                    country = map_to_country(sub_loc)
                    if country and country.lower() in country_name_to_id:
                        c_ids.append(country_name_to_id[country.lower()])
            elif loc == "Europe":
                c_ids.extend(europe_country_ids)

            line_value.update({
                'country_ids': [Command.set(list(set(c_ids)))],
                'state_ids': [Command.set(list(set(s_ids)))],
            })

            # Separate data into existing one and new one
            line_code = line_value['code']
            if line_code in existing_factors:
                write_factor_values[existing_factors[line_code]] = line_value
            else:
                new_factor_values.append(line_value)
        return new_factor_values, write_factor_values

    def _action_import_ademe_file(self):
        ademe_api_url = 'https://data.ademe.fr/data-fair/api/v1/datasets/base-carboner'
        ademe_data = self._external_api_call(ademe_api_url)
        if not ademe_data.get('updatedAt'):
            return ademe_data
        ademe_data['updatedAt'] = re.sub(r'\.\d+', '', ademe_data['updatedAt'])
        self.latest_version = datetime.datetime.strptime(ademe_data['updatedAt'], "%Y-%m-%dT%H:%M:%SZ")
        if self.last_update and self.latest_version <= self.last_update:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'message': self.env._('ADEME data is already up to date.'),
                },
            }

        required_calls = math.ceil(ademe_data['count'] / 10000)  # the api limits the amount of data lines to 10k

        _logger.info("ESG: Fetching ADEME data from their API")
        complete_data = []
        for i in range(0, required_calls):
            data_url = f'{ademe_api_url}/lines?size=10000&format=json&after={10000 * i}'
            data = self._external_api_call(data_url)
            if not data.get('results', None):
                return data
            complete_data += data['results']

        _logger.info("ESG: Reading ADEME carbon data")
        try:
            new_values, write_values = self._get_ademe_emission_factor_values(complete_data)
            _logger.info("ESG: Creating/Writing records")
            self.env['esg.emission.factor'].create(new_values)
            for record, values in write_values.items():
                record.gas_line_ids = False
                record.write(values)
            _logger.info("ESG: File imported")
        except KeyError as e:
            _logger.error(e)
            raise ValidationError(self.env._("The file format doesn't seem to be correct."))
        return True

    # =============
    # IPCC IMPORT
    # =============
    def _get_ipcc_xls_file(self, reset=False):
        request_headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        table_name = 'tmp_e63ckbntq05n963ul2451jk2sp'
        if reset:
            request_response = requests.request(
                'GET',
                'https://www.ipcc-nggip.iges.or.jp/EFDB/find_ef.php?reset=',
                timeout=(30, 30),
            )
            request_response.raise_for_status()
            request_response = requests.request(
                'POST',
                'https://www.ipcc-nggip.iges.or.jp/EFDB/find_ef.php',
                headers=request_headers,
                data={'action': 'apply_filter', 'source_data': 'default'},
                timeout=(30, 30),
            )
            request_response.raise_for_status()
            root_node = html.fromstring(request_response.content)
            if elements := root_node.xpath('//input[@name="tableName"]'):
                if len(elements) == 1:
                    table_name = elements[0].value
            cookie = request_response.headers.get('Set-Cookie', '')
            cookie_parts = [part.split('=', 1) for part in cookie.split(';') if '=' in part]
            for cookie_name, cookie_value in cookie_parts:
                if cookie_name == 'PHPSESSID':
                    request_headers['Cookie'] = f'PHPSESSID={cookie_value}'
                    break
        request_response = requests.request(
            'POST',
            'https://www.ipcc-nggip.iges.or.jp/EFDB/find_ef_xls.php',
            headers=request_headers,
            data={'lang_id': 1, 'tableName': table_name, 'mi_show_fuel': True, 'mi_show_cpool': True},
            timeout=(30, 30),
        )
        request_response.raise_for_status()
        if request_response.content:
            xls_file = BytesIO(request_response.content)
        elif not reset:
            xls_file = self._get_ipcc_xls_file(reset=True)
        else:
            raise ValidationError(self.env._("The IPCC server did not return any file to import the data."))
        return xls_file

    def _action_import_efdb_from_ipcc(self):
        response_error = {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'warning',
            },
        }
        ipcc_ef_data_list = []
        parent_source_names = set()
        try:
            from openpyxl import load_workbook  # noqa: PLC0415
            filename = self._get_ipcc_xls_file()
            workbook = load_workbook(filename=filename)
            sheet = workbook.active
            column_id_per_vals_key = {}

            for row in sheet.iter_rows():
                ipcc_data = {}
                is_header = True
                for cell in row:
                    if cell.row == 1:
                        if cell.value == 'EF ID':
                            column_id_per_vals_key[cell.column] = 'code'
                        elif cell.value == 'IPCC 1996 Source/Sink Category':
                            column_id_per_vals_key[cell.column] = 'parent_source_id'
                        elif cell.value == 'IPCC 2006 Source/Sink Category':
                            column_id_per_vals_key[cell.column] = 'source_id'
                        elif cell.value == 'Gas':
                            column_id_per_vals_key[cell.column] = 'gas_id'
                        elif cell.value == 'Description':
                            column_id_per_vals_key[cell.column] = 'name'
                        elif cell.value == 'Region / Regional Conditions':
                            column_id_per_vals_key[cell.column] = 'region'
                        elif cell.value == 'Value':
                            column_id_per_vals_key[cell.column] = 'quantity'
                        elif cell.value == 'Unit':
                            column_id_per_vals_key[cell.column] = 'unit'
                        elif cell.value == 'Technologies / Practices':
                            column_id_per_vals_key[cell.column] = 'note1'
                        elif cell.value == 'Parameters / Conditions':
                            column_id_per_vals_key[cell.column] = 'note2'
                    elif cell.column in column_id_per_vals_key:
                        is_header = False
                        key = column_id_per_vals_key[cell.column]
                        value = str(cell.value).strip()
                        if key == 'parent_source_id':
                            parent_source_names.add(value)
                        ipcc_data[key] = value
                if not is_header:
                    ipcc_ef_data_list.append(ipcc_data)
        except (ValueError, HTTPError, RequestException, ModuleNotFoundError) as exception:
            response_error['params']['message'] = self.env._(
                "Server returned an unexpected error: %(error)s",
                error=str(exception),
            )
            return response_error

        parent_sources = self.env['esg.emission.source']._load_records([{'xml_id': f'esg.ipcc_emission_source_{i}', 'noupdate': True, 'values': {'name': source_name.strip()}} for i, source_name in enumerate(parent_source_names, 1)])
        parent_source_per_name = {es.name: es for es in parent_sources}
        source_name_per_parent_source = {
            ef_data['source_id']: parent_source_per_name[ef_data['parent_source_id'].strip()]
            for ef_data in ipcc_ef_data_list
            if ef_data.get('source_id') and parent_source_per_name.get(ef_data.get('parent_source_id', '').strip())
        }
        source_per_name = {
            es.name: es
            for es in self.env['esg.emission.source']._load_records([
                {'xml_id': f'esg.ipcc_emission_source_{parent.id}_{i}', 'noupdate': True, 'values': {'name': source_name.strip(), 'parent_id': parent.id}}
                for i, (source_name, parent) in enumerate(source_name_per_parent_source.items(), 1)
            ])
        }
        gas_mapping = {
            'METHANE': self.env.ref('esg.esg_gas_ch4'),
            'CARBON DIOXIDE': self.env.ref('esg.esg_gas_co2'),
            'c-C4F8': self.env.ref('esg.esg_gas_pfc_c-c4f8'),
            'C2F6': self.env.ref('esg.esg_gas_pfc_c2f6'),
            'C3F8': self.env.ref('esg.esg_gas_pfc_c3f8'),
            'C4F6': self.env.ref('esg.esg_gas_pfc_c4f6'),
            'C4F8O': self.env.ref('esg.esg_gas_c4f8o'),
            'C5F8': self.env.ref('esg.esg_gas_pfc_c5f8'),
            'C6F14': self.env.ref('esg.esg_gas_pfc_c6f14'),
            'CARBON MONOXIDE': self.env.ref('esg.esg_gas_co'),
            'CF4': self.env.ref('esg.esg_gas_pfc_cf4'),
            'HFC-125': self.env.ref('esg.esg_gas_hfc_125'),
            'HFC-134a': self.env.ref('esg.esg_gas_hfc_134a'),
            'HFC-134a\nHFC-152a': self.env.ref('esg.esg_gas_hfc_134a'),
            'HFC-143a': self.env.ref('esg.esg_gas_hfc_143a'),
            'HFC-152a': self.env.ref('esg.esg_gas_hfc_152a'),
            'HFC-23': self.env.ref('esg.esg_gas_hfc_23'),
            'HFC-23\nHFC-32\nHFC-125\nHFC-134a\nHFC-143a\nCF4\nC2F6\nC3F8\nC4F8\nC5F8\nC6F14': self.env.ref('esg.esg_gas_hfc_23'),
            'HFC-23\nHFC-32\nHFC-125\nHFC-134a\nHFC-152a\nHFC-143a\nHFC-227ea\nHFC-236fa': self.env.ref('esg.esg_gas_hfc_23'),
            'HFC-23\nHFC-32\nHFC-41\nHFC-43-10mee\nHFC-125\nHFC-134\nHFC-134a\nHFC-152a\nHFC-143\nHFC-143a\nHFC-227ea\nHFC-236fa\nHFC-245ca\nCF4\nC2F6\nC3F8\nC4F10\nc-C4F8\nC5F12\nC6F14': self.env.ref('esg.esg_gas_hfc_23'),
            'HFC-23\nHFC-32\nHFC-41\nHFC-43-10mee\nHFC-125\nHFC-134\nHFC-134a\nHFC-152a\nHFC-143\nHFC-143a\nHFC-227ea\nHFC-236fa\nHFC-245ca\nHFC-152\nHFC-161\nHFC-236cb\nHFC-236ea\nHFC-245fa\nHFC-365mfc': self.env.ref('esg.esg_gas_hfc_23'),
            'HFC-32': self.env.ref('esg.esg_gas_hfc_32'),
            'HFC-41': self.env.ref('esg.esg_gas_hfc_41'),
            'HFE-125\nHFC-43-10mee\nHFC-125\nHFC-134\nHFC-134a\nHFC-152a\nHFC-143\nHFC-143a\nHFC-227ea\nHFC-236fa\nHFC-245ca\nHFC-152\nHFC-161\nHFC-236cb\nHFC-236ea\nHFC-245fa\nHFC-365mfc': self.env.ref('esg.esg_gas_cf3ochf2'),
            'HFE-245fa1\nHFE-365mcf3\nHFC-134a\nHFC-152a\nHFC-227ea': self.env.ref('esg.esg_gas_chf2ch2ocf3'),
            'HFE-245fa1\nHFE-365mcf3\nHFC-43-10mee\nHFC-134a\nHFC-152a\nHFC-227ea': self.env.ref('esg.esg_gas_chf2ch2ocf3'),
            'HFE-365mcf3\nHFC-43-10mee\nC6F14': self.env.ref('esg.esg_gas_cf3cf2ch2och3'),
            'HFE-7100': self.env.ref('esg.esg_gas_chf2_c4f9och3'),
            'METHANE\nCARBON DIOXIDE\nNITROUS OXIDE': self.env.ref('esg.esg_gas_ch4'),
            'METHANE\nNITROUS OXIDE': self.env.ref('esg.esg_gas_ch4'),
            "NITROGEN OXIDES (NO+NO2)\nMETHANE\nCARBON MONOXIDE\nCARBON DIOXIDE\nNITROUS OXIDE": self.env.ref('esg.esg_gas_co'),
            "NITROGEN OXIDES (NO+NO2)\nMETHANE\nCARBON MONOXIDE\nNITROUS OXIDE": self.env.ref('esg.esg_gas_co'),
            'Nitrogen Trifluoride': self.env.ref('esg.esg_gas_nf3'),
            "Nitrogen Trifluoride\nHFC-23\nHFC-32\nCF4\nC2F6\nC3F8\nc-C4F8\nSulphur Hexafluoride": self.env.ref('esg.esg_gas_nf3'),
            'NITROUS OXIDE': self.env.ref('esg.esg_gas_n2o'),
            "SULPHUR DIOXIDE (SO2+SO3)\nNITROGEN OXIDES (NO+NO2)\nNON METHANE VOLATILE ORGANIC COMPOUNDS\nMETHANE\nCARBON MONOXIDE\nCARBON DIOXIDE\nNITROUS OXIDE": self.env.ref('esg.esg_gas_so2'),
            "Sulphur Hexafluoride": self.env.ref('esg.esg_gas_sf6'),
        }

        def parse_float(value):
            amount = None
            with contextlib.suppress(ValueError, TypeError):
                amount = float(value)
            return amount

        emission_factor_xmlid_list = []
        uom_kg = self.env.ref('uom.product_uom_kgm')
        uom_unit = self.env.ref('uom.product_uom_unit')
        uom_m3 = self.env.ref('uom.product_uom_cubic_meter')
        uom_tonne = self.env.ref('uom.product_uom_ton')
        uom_ha, uom_lto = self.env['uom.uom']._load_records([
            {'xml_id': 'esg.uom_ha', 'noupdate': True, 'values': {'name': 'ha', 'relative_factor': 1}},
            {'xml_id': 'esg.uom_lt', 'noupdate': True, 'values': {'name': 'LTO', 'relative_factor': 1}},
        ])
        nb_skipped_records = 0
        for ef_data in ipcc_ef_data_list:
            code = ef_data['code']
            note = ef_data.get('note1', '')
            uom = uom_kg
            gaz_id = False
            source_id = False
            name = ef_data['name'].strip()
            if not name:
                id = int(code)
                if 327476 <= id <= 327568:
                    name = "Combustion factor (Cf) for fires in vegetation types"
                elif 327569 <= id <= 327644:
                    name = "Below-ground biomass (BGB): root-to-shoot ratio"
                elif 327645 <= id <= 328060:
                    name = "Above-ground biomass (AGB): net biomass growth in natural forests"
                elif 327427 <= id <= 327475:
                    name = "Soil organic carbon stocks (SOCREF) in mineral soils"
                elif 327386 <= id <= 327426:
                    name = "Dead wood carbon stock"
                elif 327260 <= id <= 327385:
                    name = "Litter carbon stock"
                else:
                    nb_skipped_records += 1
                    continue
            if source_name := ef_data['source_id'].strip():
                source = source_per_name.get(source_name)
                if not source:
                    nb_skipped_records += 1
                    continue
                source_id = source.id
            else:
                parent_source = parent_source_per_name.get(ef_data['parent_source_id'].strip())
                if not parent_source:
                    nb_skipped_records += 1
                    continue
                source_id = parent_source.id
            if gaz := gas_mapping.get(ef_data['gas_id']):
                gaz_id = gaz.id
            else:
                nb_skipped_records += 1
                continue
            if note2 := ef_data.get('note2', ''):
                note += '\n' + note2
            value = parse_float(ef_data['quantity'])
            if value is None:
                nb_skipped_records += 1
                continue
            if unit := ef_data.get('unit'):
                if unit.startswith('%') or unit.lower().startswith('fraction') or unit.lower().startswith('year') or unit in ['per year', 'months', 'parts per billion by volume', 'asse', 'installe', 'equipment']:
                    nb_skipped_records += 1
                    continue
                elif unit.startswith('g'):
                    value /= 1000
                elif (
                    unit.lower().startswith('kg')
                ):
                    value *= 1
                elif unit.startswith('TJ'):
                    value *= 1.11 * (10 ** -5)
                elif unit.lower().startswith('gg'):
                    value *= 10 ** 9
                elif unit.lower().startswith('ton') or unit in ['(kg PFC/tAl)/(AE-Minutes/cellday)', '(kg PFC/tAl)/(mV/day)', 'kg SF6/tonnes magnesium produced or smelted']:
                    uom = uom_tonne
                elif unit == 'm3/m3 beer':
                    value *= 1.020
                    uom = uom_m3
                elif unit == 'm3/m3 ethanol':
                    value *= 789
                    uom = uom_m3
                elif unit == 'kg CH4/head/yr':
                    uom = uom_unit
                elif unit == 't dm/ha':
                    uom = uom_ha
                    value *= 1000
                elif unit == 'kg/LTO':
                    uom = uom_lto
                note += '\nUnit converted in kg: ' + unit
            emission_factor_xmlid_list.append({
                'xml_id': f'esg.ipcc_emission_factor_{code}',
                'noupdate': True,
                'values': {
                    'code': code,
                    'name': name,
                    'description': note,
                    'uom_id': uom.id,
                    'source_id': source_id,
                    'region': ef_data['region'],
                    'database_id': self.id,
                    'gas_line_ids': [
                        Command.create({
                            'gas_id': gaz_id,
                            'quantity': value,
                        }),
                    ],
                },
            })
        if nb_skipped_records:
            _logger.warning("%s entries from IPCC Database were skipped because of missing information", nb_skipped_records)
        self.env['esg.emission.factor']._load_records(emission_factor_xmlid_list)
        return True
