# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re
from odoo import api, models, _
from collections import defaultdict


class AccountGeneralLedgerReportHandler(models.AbstractModel):
    _inherit = 'account.general.ledger.report.handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options)
        if self.env.company.account_fiscal_country_id.code == 'BG':
            options.setdefault('buttons', []).append({
                'name': _('SAF-T Monthly'),
                'sequence': 50,
                'action': 'export_file',
                'action_param': 'l10n_bg_export_saft_to_xml',
                'file_export_type': _('XML'),
            })

    @api.model
    def _l10n_bg_saft_fill_saft_account_by_code(self, values):
        saft_account_by_code = {
            account_vals['account'].code: account_vals['account'].l10n_bg_saft_account_code
            for account_vals in values['account_vals_list']
        }
        values['saft_account_by_code'] = saft_account_by_code

    @api.model
    def _l10n_bg_saft_check_header_values(self, values):
        """ Check whether the company configuration is correct for filling in the Header. """

        if not values['company'].l10n_bg_saft_tax_accounting_basis:
            values['errors']['settings_accounting_basis_missing'] = {
                'message': _('Tax Accounting Basis is not set.'),
                'action_text': _('View Company'),
                'action': values['company']._get_records_action(name=self.env._('Company missing Tax Accounting Basis')),
                'level': 'danger',
            }

        if not values['company'].l10n_bg_saft_tax_entity_type:
            values['errors']['company_tax_entity_type_missing'] = {
                'message': _('The Tax Entity Type is not set.'),
                'action_text': _('View Company'),
                'action': values['company']._get_records_action(name=self.env._('Company missing Tax Entity Type')),
                'level': 'danger',
            }

        if not values['company'].l10n_bg_saft_ownership_structure:
            values['errors']['settings_ownership_structure_missing'] = {
                'message': _('The Ownership Structure is not set.'),
                'action_text': _('View Company'),
                'action': values['company']._get_records_action(name=self.env._('Company missing Ownership Structure')),
                'level': 'danger',
            }

        # Ultimate Owners
        elif values['company'].l10n_bg_saft_ownership_structure in ('3', '4'):
            # If they are part of a group, they have to declare ultimate owners
            if not values['company'].l10n_bg_saft_ultimate_owner_ids:
                values['errors']['ultimate_owners_missing'] = {
                    'message': _('Missing Ultimate Owners.'),
                    'action_text': _('View Company'),
                    'action': values['company']._get_records_action(name=self.env._('Company without Ultimate Owner')),
                    'level': 'danger',
                }
            else:
                ultimate_owners = values['company'].l10n_bg_saft_ultimate_owner_ids
                ultimate_owners_not_company = self.env['res.partner']
                ultimate_owners_missing_country = self.env['res.partner']
                bg_ultimate_owners_missing_vat = self.env['res.partner']
                bg_ultimate_owners_missing_cyrillic_name = self.env['res.partner']

                for owner in ultimate_owners:
                    if not owner.is_company:
                        ultimate_owners_not_company += owner
                    if not owner.country_code:
                        ultimate_owners_missing_country += owner
                    elif owner.country_code == 'BG':
                        if not owner.vat or (not owner.vat.isnumeric() and not owner.vat.startswith('BG')):
                            bg_ultimate_owners_missing_vat += owner
                        if not self._check_cyrillic_name(owner.name):
                            bg_ultimate_owners_missing_cyrillic_name += owner

                ultimate_owner_vals_list = {
                    "ultimate_owner_name_cyrillic_bg": [],
                    "ultimate_owner_uicbg": [],
                    "ultimate_owner_name_cyrillic_foreign": [],
                    "ultimate_owner_name_latin_foreign": [],
                    "country_foreign": [],
                }
                for owner in sorted(ultimate_owners
                                    - ultimate_owners_not_company
                                    - ultimate_owners_missing_country
                                    - bg_ultimate_owners_missing_vat
                                    , key=lambda owner: owner.name):  # Sorted for deterministic tests
                    ultimate_owner_vals_list["ultimate_owner_name_cyrillic_bg"].append(owner.name if owner.country_code in 'BG' else '00')
                    ultimate_owner_vals_list["ultimate_owner_uicbg"].append('00' if owner.country_code not in 'BG' else (owner.vat if owner.vat.isnumeric() else owner.vat[2:]))
                    ultimate_owner_vals_list["ultimate_owner_name_cyrillic_foreign"].append(owner.name if self._check_cyrillic_name(owner.name) and owner.country_code not in 'BG' else '00')
                    ultimate_owner_vals_list["ultimate_owner_name_latin_foreign"].append(owner.name if not self._check_cyrillic_name(owner.name) and owner.country_code not in 'BG' else '00')
                    ultimate_owner_vals_list["country_foreign"].append(owner.country_code)

                values["ultimate_owner_vals_list"] = ultimate_owner_vals_list

                if ultimate_owners_not_company:
                    values['errors']['ultimate_owners_not_company'] = {
                        'message': _('Ultimate Owners that are not companies.'),
                        'action_text': _('View Ultimate Owners'),
                        'action': ultimate_owners_not_company._get_records_action(name=self.env._('Ultimate Owners not companies')),
                        'level': 'warning',
                    }
                if ultimate_owners_missing_country:
                    values['errors']['ultimate_owners_missing_country'] = {
                        'message': _('Ultimate Owners without a Country.'),
                        'action_text': _('View Ultimate Owners'),
                        'action': ultimate_owners_missing_country._get_records_action(name=self.env._('Ultimate Owners without a Country')),
                        'level': 'danger',
                    }
                if bg_ultimate_owners_missing_vat:
                    values['errors']['bg_ultimate_owners_missing_vat'] = {
                        'message': _('Bulgarian Ultimate 0wners without a VAT Number.'),
                        'action_text': _('View Ultimate Owners'),
                        'action': bg_ultimate_owners_missing_vat._get_records_action(name=self.env._('Ultimate Owners without a VAT Number')),
                        'level': 'danger',
                    }
                if bg_ultimate_owners_missing_cyrillic_name:
                    values['errors']['bg_ultimate_owners_missing_cyrillic_name'] = {
                        'message': _('Bulgarian Ultimate Owners without a cyrillic name.'),
                        'action_text': _('View Ultimate Owners'),
                        'action': bg_ultimate_owners_missing_cyrillic_name._get_records_action(name=self.env._('Ultimate Owners without a cyrillic name')),
                        'level': 'danger',
                    }

        # Beneficial Owners
        if values['company'].l10n_bg_saft_beneficial_owner_ids:

            beneficial_owners = values['company'].l10n_bg_saft_beneficial_owner_ids
            beneficial_owners_not_person = self.env['res.partner']
            beneficial_owners_missing_country = self.env['res.partner']
            bg_beneficial_owners_missing_egn = self.env['res.partner']
            bg_beneficial_owners_missing_cyrillic_name = self.env['res.partner']
            foreign_beneficial_owners_missing_latin_name = self.env['res.partner']

            for owner in beneficial_owners:
                if owner.is_company:
                    beneficial_owners_not_person += owner
                if not owner.country_code:
                    beneficial_owners_missing_country += owner
                elif owner.country_code == 'BG':
                    if not owner._get_additional_identifier('BG_CN'):
                        bg_beneficial_owners_missing_egn += owner
                    if not self._check_cyrillic_name(owner.name):
                        bg_beneficial_owners_missing_cyrillic_name += owner
                elif owner.country_code != 'BG' and self._check_cyrillic_name(owner.name):
                    foreign_beneficial_owners_missing_latin_name += owner

            beneficial_owner_vals_list = {
                "beneficial_owner_name_cyrillic_bg": [],
                "beneficial_owner_egn": [],
                "beneficial_owner_name_latin_foreign": [],
                "beneficial_country_foreign": [],  # Citizenship of the beneficial owner - Country code
                "beneficial_country_foreign_code": [],  # Country of residence of the beneficial owner - Country code
            }

            for owner in sorted(beneficial_owners
                          - beneficial_owners_not_person
                          - beneficial_owners_missing_country
                          - bg_beneficial_owners_missing_egn
                          , key=lambda owner: owner.name):  # Sorted for deterministic tests

                beneficial_owner_vals_list["beneficial_owner_name_cyrillic_bg"].append(owner.name if owner.country_code in 'BG' else '00')
                beneficial_owner_vals_list["beneficial_owner_egn"].append(owner._get_additional_identifier('BG_CN') if owner.country_code in 'BG' else '00')
                beneficial_owner_vals_list["beneficial_owner_name_latin_foreign"].append(owner.name if owner.country_code not in 'BG' else '00')

                # We don't differenciate country_codes and simply use the country_code provided
                # by the partner to avoid clutering the model with more fields used only in edge cases.
                beneficial_owner_vals_list["beneficial_country_foreign"].append(owner.country_code)  # Citizenship of the beneficial owner - Country code
                beneficial_owner_vals_list["beneficial_country_foreign_code"].append(owner.country_code)  # Country of residence of the beneficial owner - Country code

            values["beneficial_owner_vals_list"] = beneficial_owner_vals_list

            if beneficial_owners_not_person:
                values['errors']['beneficial_owners_not_person'] = {
                    'message': _('Beneficial Owners that are not Persons.'),
                    'action_text': _('View Beneficial Owners'),
                    'action': beneficial_owners_not_person._get_records_action(name=self.env._('Beneficial Owners not persons')),
                    'level': 'warning',
                }
            if beneficial_owners_missing_country:
                values['errors']['beneficial_owners_missing_country'] = {
                    'message': _('Beneficial Owners without a Country.'),
                    'action_text': _('View Beneficial Owners'),
                    'action': beneficial_owners_missing_country._get_records_action(name=self.env._('Beneficial Owners without a Country')),
                    'level': 'danger',
                }
            if bg_beneficial_owners_missing_egn:
                values['errors']['bg_beneficial_owners_missing_egn'] = {
                    'message': _('Bulgarian Beneficial Owners without an EGN.'),
                    'action_text': _('View Beneficial Owners'),
                    'action': bg_beneficial_owners_missing_egn._get_records_action(name=self.env._('Beneficial Owners without EGN')),
                    'level': 'danger',
                }
            if bg_beneficial_owners_missing_cyrillic_name:
                values['errors']['bg_beneficial_owners_missing_cyrillic_name'] = {
                    'message': _('Bulgarian Beneficial Owners without a cyrillic name.'),
                    'action_text': _('View Beneficial Owners'),
                    'action': bg_beneficial_owners_missing_cyrillic_name._get_records_action(name=self.env._('Bulgarian Beneficial Owners without a cyrillic name')),
                    'level': 'danger',
                }
            if foreign_beneficial_owners_missing_latin_name:
                values['errors']['foreign_beneficial_owners_missing_latin_name'] = {
                    'message': _('Foreign Beneficial Owners without a latin name.'),
                    'action_text': _('View Beneficial Owners'),
                    'action': foreign_beneficial_owners_missing_latin_name._get_records_action(name=self.env._('Foreign Beneficial Owners without a Latin name')),
                    'level': 'danger',
                }

        if not values['company'].bank_ids:
            values['errors']['company_bank_account_missing'] = {
                'message': _('Company without a Bank Account.'),
                'action_text': _('View Company/ies'),
                'action': values['company'].partner_id._get_records_action(name=_("Companies missing Bank Account")),
                'level': 'danger',
            }
        else:
            bank_account_with_missing_bank_name = self.env['res.partner.bank']
            bank_account_with_missing_registration_number = self.env['res.partner.bank']
            bank_account_with_missing_country = self.env['res.partner.bank']
            for bank_account in values['company'].bank_ids:
                if bank_account.account_type != 'iban' and not bank_account.l10n_bg_saft_registration_number:
                    bank_account_with_missing_registration_number += bank_account
                if bank_account.account_type != 'iban' and not bank_account.bank_name:
                    bank_account_with_missing_bank_name += bank_account
                if bank_account.account_type != 'iban' and not bank_account.country_code:
                    bank_account_with_missing_country += bank_account
            if bank_account_with_missing_bank_name:
                values['errors']['bank_account_with_missing_bank_name'] = {
                    'message': _('Bank Accounts without a Bank Name'),
                    'action_text': _('View Bank Accounts'),
                    'action': bank_account_with_missing_bank_name._get_records_action(name=_("Bank accounts missing a bank name")),
                    'level': 'danger',
                }
            if bank_account_with_missing_registration_number:
                values['errors']['bank_account_with_missing_registration_number'] = {
                    'message': _('Bank Accounts without a Bank Registration Number'),
                    'action_text': _('View Bank Accounts'),
                    'action': bank_account_with_missing_registration_number._get_records_action(name=_("Bank accounts missing a Bank Registration Number")),
                    'level': 'danger',
                }
            if bank_account_with_missing_country:
                values['errors']['bank_account_with_missing_country'] = {
                    'message': _('Bank Accounts without a Country'),
                    'action_text': _('View Bank Accounts'),
                    'action': bank_account_with_missing_country._get_records_action(name=_("Bank accounts missing a Country")),
                    'level': 'danger',
                }

        def get_company_action(message):
            return {
                'message': message,
                'action_text': self.env._("View Company/ies"),
                'action': values['company']._get_records_action(name=self.env._('Invalid Company/ies')),
                'level': 'danger',
            }

        partner = values['company'].partner_id
        if not partner.vat:
            values['errors']['company_vat_number_missing'] = get_company_action(_('Company without a VAT number.'))

        company_contact = self.env['res.partner']
        if contacts := values['partner_detail_map'][self.env.company.partner_id.id]['contacts']:
            company_contact |= contacts[0]

        def get_company_contact_action(message):
            return {
                'message': message,
                'action_text': self.env._("View Company Contact"),
                'action': company_contact._get_records_action(name=self.env._('Invalid Company/ies')),
                'level': 'danger',
            }

        if company_contact and not company_contact.phone:
            values['errors']['missing_partner_phone_number'] = get_company_contact_action(_('Company Contact without a phone number.'))

        if company_contact and not company_contact.function:
            values['errors']['missing_partner_function'] = get_company_contact_action(_('Company Contact without a job title.'))

        if company_contact and not company_contact.email:
            values['errors']['missing_partner_email'] = get_company_contact_action(_('Company Contact without an email.'))

        if company_contact and not re.search(r'\s', company_contact.name):
            values['errors']['missing_partner_last_name'] = get_company_contact_action(_('Company Contact without a last name.'))

    def _l10n_bg_saft_fill_customer_supplier_code(self, partner):

        """ Unique identification number of the economic operator issued by the state administration
        Unique customer/supplier code consisting of: type (two-digit code) followed by the unique customer/supplier code as follows:
            10 + EIK (BG): the unique identification code for economic operators registered in Bulgaria.
            11 + CC + VAT (EU non BG) : the unique VAT identification code of the relevant EU member state verifiable through the VAT Information Exchange System - Example: 11EL123456789 or 11HU12345678
            12 + CC + VAT (non EU): when available, a unique VAT identification code or other code from an official register of the respective non EU country - Example: 12TK123005284
            13 + EGN (BG):  for natural persons/Bulgarian citizens or 13 followed by a unique personal code for natural persons residing in Bulgaria.
            14 + CC + Code: a unique code of the economic operator, appended by the obliged person (usually generated by an information system).
                fallback for missing unique code
            15 + Code: a unique code of the economic operator added by the obliged person (usually generated by an information system).
                fallback for missing country code and unique code
            16 + SN: a service number provided by the NRA (starting with 307...).

        With the following:
            CC: 2 letters country code according to ISO 3166-1
            UIC / CUI / EIK:  unique 9-digit number (+4 for branch)
            VAT Number: for companies registered for VAT with the NRA (BG + 9-digit EIK (e.g., BG123456789))
            EGN: Uniform Civil Number: unique 10-digit number assigned to every
                Bulgarian citizen at birth and to foreigners who receive permanent residency.
        """
        if (partner.country_code and partner.country_code == 'BG') or (partner.vat and partner.vat.upper().startswith('BG')):
            if not partner.is_company and partner._get_additional_identifier('BG_CN'):
                return '13' + partner._get_additional_identifier('BG_CN')
            if not partner.is_company and partner.vat and partner.vat.isnumeric():
                return '13' + partner.vat
            if not partner.is_company and partner.vat:
                return '13' + partner.vat[2:]
            if partner._get_additional_identifier('BG_CN'):
                return '10' + partner._get_additional_identifier('BG_CN')
            if partner.vat and partner.vat.isnumeric():
                return '10' + partner.vat
            if partner.vat:
                return '10' + partner.vat[2:]
            return '14' + 'BG' + str(partner.id)
        if partner.country_id and partner.country_id.country_group_codes and \
                ('EU' in partner.country_id.country_group_codes or
                'EU_PREFIX' in partner.country_id.country_group_codes):
            if partner.vat and partner.vat.isnumeric():
                return '11' + partner.country_code + partner.vat
            if partner.vat:
                return '11' + partner.vat
            return '14' + partner.country_code + str(partner.id)
        if partner.country_code:
            if partner.vat and partner.vat.upper().startswith(partner.country_code):
                return '12' + partner.vat
            if partner.vat:
                return '12' + partner.country_code + partner.vat
            return '14' + partner.country_code + str(partner.id)
        return '15' + str(partner.id)

    def _l10n_bg_saft_update_partner_detail_map(self, values):
        related_partners = values['company'].l10n_bg_saft_related_partner_ids.ids
        faulty_partners = defaultdict(lambda: self.env['res.partner'])

        for partner_info in values['partner_detail_map'].values():

            partner = partner_info['partner']

            if not partner.name:
                faulty_partners['partner_missing_name'] |= partner
            else:
                partner_info['is_name_cyrillic'] = self._check_cyrillic_name(partner_info['partner'].name)

            if not partner.city:
                faulty_partners['partner_city_missing'] |= partner

            partner_info['saft_operator_code'] = self._l10n_bg_saft_fill_customer_supplier_code(partner_info['partner'])
            if (partner_info['saft_operator_code'].startswith('14')
                    or partner_info['saft_operator_code'].startswith('15')
                    or not partner.country_code
                    or (
                        not partner._get_additional_identifier('BG_CN') and
                        not partner.vat)):
                faulty_partners['partners_with_incomplete_identification'] |= partner

            partner_info['is_related'] = partner_info['partner'].id in related_partners

        descriptions = {
            "partner_city_missing": (_("Partners without a city."), "danger"),
            "partner_country_missing": (_("Partners without a country"), "danger"),
            "partner_missing_name": (_("Partners without a name:"), "danger"),
            "partners_with_incomplete_identification": (_("Partners without a country or identification number (Company ID or VAT)"), "danger"),
        }
        values['errors'] |= {
            key: {
                'message': descriptions[key][0],
                'action_text': self.env._('View Partners'),
                'action': partners._get_records_action(name=self.env._("Invalid Partner(s)")),
                'level': descriptions[key][1],
            }
            for key, partners in faulty_partners.items()
        }

    def _l10n_bg_saft_check_saft_accounts(self, values):

        encountered_account_ids = [account_vals['account']['id'] for account_vals in values['account_vals_list']]
        accounts_missing_saft_code = self.env['account.account'].search([
            ('id', 'in', encountered_account_ids),
            ('l10n_bg_saft_account_code', '=', False),
            '|', ('active', '=', True), ('active', '=', False),  # prevent inactive accounts from being filtered out if used in a journal entry
        ])

        if accounts_missing_saft_code:
            values['errors']['accounts_missing_saft_code'] = {
                'message': _('Accounts without a SAF-T Code'),
                'action_text': _('View Accounts'),
                'action': accounts_missing_saft_code._get_records_action(
                    name=_("Accounts without a SAF-T Code")),
                'level': 'danger',
            }

    @api.model
    def _l10n_bg_saft_check_tax_values(self, values):
        """ Check whether all taxes have a Bulgarian SAFT tax code on them. """

        encountered_tax_ids = [tax_vals['id'] for tax_vals in values['tax_vals_list']]
        taxes_missing_saft_code = self.env['account.tax'].search([
            ('id', 'in', encountered_tax_ids),
            ('l10n_bg_saft_tax_code', '=', False),
            '|', ('active', '=', True), ('active', '=', False),  # prevent inactive taxes from being filtered out if used in a document
        ])
        if taxes_missing_saft_code:
            values['errors']['taxes_missing_saft_code'] = {
                'message': _('Taxes without a SAF-T Tax Code.'),
                'action_text': _('View Taxes'),
                'action': taxes_missing_saft_code._get_records_action(name=_("Taxes without a SAF-T Tax Code.")),
                'level': 'danger',
            }

    @api.model
    def _l10n_bg_saft_fill_tax_values(self, values):
        """ Fill in the Bulgarian tax type, tax type description (in Bulgarian, if available), and tax code. """

        tax_type_description_per_tax_code = {
            "100": "ДАНЪК ВЪРХУ ДОБАВЕНАТА СТОЙНОСТ ",
            "200": "КОРПОРАТИВЕН ДАНЪК ",
            "300": "ДАНЪК ВЪРХУ ПРИХОДИТЕ НА БЮДЖЕТНИТЕ ПРЕДПРИЯТИЯ ПО ЗКПО",
            "400": "ДАНЪК ВЪРХУ ДОПЪЛНИТЕЛНИТЕ РАЗХОДИ НА НАРОДНИТЕ ПРЕДСТАВИТЕЛИ ПО ЗКПО",
            "500": "ДАНЪК ВЪРХУ ХАЗАРТНАТА ДЕЙНОСТ ПО ЗКПО",
            "600": "ДАНЪК ВЪРХУ РАЗХОДИТЕ",
            "700": "ДАНЪК ПРИ ИЗТОЧНИКА",
            "800": "ДАНЪК ВЪРХУ ДЕЙНОСТТА ОТ ОПЕРИРАНЕ НА КОРАБИ",
            "900": "ВРЕМЕННА СОЛИДАРНА ВНОСКА ПО РЕГЛАМЕНТ 2022/1854",
            "910": "ДАНЪК ВЪРХУ ЗАСТРАХОВАТЕЛНИТЕ ПРЕМИИ",
            "915": "ДОПЪЛНИТЕЛЕН ДАНЪК И НАЦИОНАЛЕН ДОПЪЛНИТЕЛЕН ДАНЪК ПО ГЛАВА ПЕТА ''А'' ОТ ЗКПО",
            "920": "ДАНЪК ВЪРХУ ОБЩАТА ГОДИШНА ДАНЪЧНА ОСНОВА ПО ЗДДФЛ",
            "930": "ДАНЪК ВЪРХУ ГОДИШНАТА ДАНЪЧНА ОСНОВА ЗА ДОХОДИ ОТ СТОПАНСКА ДЕЙНОСТ КАТО ЕДНОЛИЧЕН ТЪРГОВЕЦ ПО ЗДДФЛ",
            "940": "ДЪРЖАВНО ОБЩЕСТВЕНО ОСИГУРЯВАНЕ ",
            "950": "ФОНД ДЗПО",
            "960": "ЗДРАВНО ОСИГУРЯВАНЕ",
            "970": "УЧИТЕЛСКИ ПЕНСИОНЕН ФОНД",
            "980": "ФОНД ГВРС",
            "990": "ТАКСИ ПО ЗАКОНА ЗА ХАЗАРТА",
            "991": "Закон за акцизите и данъчните складове",
            "111": "Общ код за лихви и санкции",
        }

        encountered_tax_ids = [tax_vals['id'] for tax_vals in values['tax_vals_list']]
        encountered_taxes = self.env['account.tax'].browse(encountered_tax_ids)
        tax_fields_by_id = {
            tax.id: {
                'l10n_bg_saft_tax_type': tax.l10n_bg_saft_tax_code[:3] if tax.l10n_bg_saft_tax_code else '',
                'l10n_bg_saft_tax_type_description': tax_type_description_per_tax_code[tax.l10n_bg_saft_tax_code[:3]] if tax.l10n_bg_saft_tax_code else '',
                'l10n_bg_saft_tax_code': tax.l10n_bg_saft_tax_code or '',
                'country_code': tax.country_code,
            }
            for tax in encountered_taxes
        }

        for line_vals in values['tax_detail_per_line_map'].values():
            for tax_detail_vals in line_vals['tax_detail_vals_list']:
                tax_fields = tax_fields_by_id[tax_detail_vals['tax_id']]
                tax_detail_vals.update(tax_fields)

        values['tax_type_vals_list'] = {}

        for tax_vals in values['tax_vals_list']:
            tax_fields = tax_fields_by_id[tax_vals['id']]
            tax_vals.update(tax_fields)
            values['tax_type_vals_list'].setdefault(tax_vals['l10n_bg_saft_tax_type'], {
                'l10n_bg_saft_tax_type': tax_vals['l10n_bg_saft_tax_type'],
                'l10n_bg_saft_tax_type_description': tax_vals['l10n_bg_saft_tax_type_description'],
                'tax_vals_list': [],
            })['tax_vals_list'].append(tax_vals)

    @api.model
    def _l10n_bg_saft_fill_uom_values(self, values):
        encountered_product_uom_ids = sorted({
            line_vals['product_uom_id']
            for move_vals in values['move_vals_list']
            for line_vals in move_vals['line_vals_list']
            if line_vals['product_uom_id']
        })
        uom_vals_list = self.env['uom.uom'].browse(encountered_product_uom_ids)
        values['uom_vals_list'] = uom_vals_list

    @api.model
    def _l10n_bg_saft_check_uom_values(self, values):
        uom_with_missing_saft_code = self.env['uom.uom']
        uom_with_missing_saft_description = self.env['uom.uom']
        for uom_id in values['uom_vals_list']:
            if not uom_id.l10n_bg_saft_uom_code:
                uom_with_missing_saft_code += uom_id
            if not uom_id.l10n_bg_saft_uom_description:
                uom_with_missing_saft_description += uom_id

        if uom_with_missing_saft_code:
            values['errors']['uom_with_missing_saft_code'] = {
                'message': _('Units without a SAF-T UoM Code.'),
                'action_text': _('View Units'),
                'action': uom_with_missing_saft_code._get_records_action(name=_("Units without a SAF-T UoM Code")),
                'level': 'danger',
            }
        if uom_with_missing_saft_description:
            values['errors']['uom_with_missing_saft_description'] = {
                'message': _('Units without a SAF-T UoM Description.'),
                'action_text': _('View Units'),
                'action': uom_with_missing_saft_description._get_records_action(name=_("Units without a SAF-T UoM Description")),
                'level': 'danger',
            }

    @api.model
    def _l10n_bg_saft_fill_product_values(self, values):
        """ Check whether each product has a ref, no products have duplicate refs,
            and that each product has an Intrastat Code. """
        def get_product_action(message, products, level='warning'):
            return {
                'message': message,
                'action_text': self.env._('View Product(s)'),
                'action': products._get_records_action(name=self.env._("Invalid Product(s)")),
                'level': level,
            }

        encountered_product_ids = sorted({
            line_vals['product_id']
            for move_vals in values['move_vals_list']
            for line_vals in move_vals['line_vals_list']
            if line_vals['product_id']
        })
        encountered_products = self.env['product.product'].browse(encountered_product_ids)
        products_without_intrastat_code = encountered_products.filtered(lambda p: p.type != 'service' and not p.intrastat_code_id)

        if products_without_intrastat_code:
            values['errors']['product_intrastat_code_missing'] = get_product_action(
                _("Product without an Intrastat Commodity code."),
                products_without_intrastat_code,
                level='danger',
            )

        products_no_ref = encountered_products.filtered(lambda product: not product.default_code)
        products_with_ref = (encountered_products - products_no_ref)
        products_per_ref = products_with_ref.grouped("default_code")
        products_dup_ref = self.env['product.product']

        for products in products_per_ref.values():
            if len(products) >= 2:
                products_dup_ref |= products

        if products_no_ref:
            values['errors']['product_internal_reference_missing'] = get_product_action(
                _('Products without an Internal Reference.'),
                products_no_ref,
                level='danger',
            )
        if products_dup_ref:
            values['errors']['product_internal_reference_duplicated'] = get_product_action(
                _('Products with duplicated Internal Reference.'),
                products_dup_ref,
                level='danger',
            )

        product_vals_list = [
            {
                'id': product.id,
                'name': product.name,
                'default_code': product.default_code,
                'uom_base': product.uom_id.name,
                'uom_standard': product.uom_id.l10n_bg_saft_uom_code,
                'uom_conversion_factor': product.uom_id.l10n_bg_saft_uom_conversion_factor,
                'goods_services_code': '02' if product.type == 'service' else '01',
                'product_category': product.product_tmpl_id.categ_id.name,
                'commodity_code': '00000000' if product.type == 'service' else
                    (product.intrastat_code_id.code if product.intrastat_code_id else '0'),
            }
            for product in encountered_products
        ]
        values['product_vals_list'] = product_vals_list

    @api.model
    def _l10n_bg_saft_fill_invoice_values(self, values):
        sale_invoice_vals = {
            'total_debit': 0.0,
            'total_credit': 0.0,
            'number': 0,
            'move_vals_list': [],
        }
        purchase_invoice_vals = {
            'total_debit': 0.0,
            'total_credit': 0.0,
            'number': 0,
            'move_vals_list': [],
        }
        encountered_invoices_ids = [
            move_vals['id']
            for move_vals in values['move_vals_list']
            if move_vals['type'] in {'out_invoice', 'out_refund', 'in_invoice', 'in_refund'}
        ]
        encountered_invoices = self.env['account.move'].browse(encountered_invoices_ids)

        invoice_detail_map = {
            invoice.id: invoice
            for invoice in encountered_invoices
        }

        for move_vals in values['move_vals_list']:
            if move_vals['id'] not in invoice_detail_map:
                continue
            invoice_detail = invoice_detail_map[move_vals['id']]

            move_vals.update({
                'invoice_line_vals_list': [],
                'l10n_bg_saft_invoice_type': invoice_detail['l10n_bg_document_type'],
                'l10n_bg_saft_self_billing_indicator': 'Y' if invoice_detail['journal_id'].is_self_billing else 'N',
            })

            dict_to_update = sale_invoice_vals if move_vals['type'] in {'out_invoice', 'out_refund'} else purchase_invoice_vals
            for line_vals in move_vals['line_vals_list']:
                if line_vals['account_type'] not in ('asset_receivable', 'liability_payable') and line_vals['display_type'] == 'product':
                    dict_to_update['total_debit'] += line_vals['debit']
                    dict_to_update['total_credit'] += line_vals['credit']
                    move_vals['invoice_line_vals_list'].append(line_vals)

            dict_to_update['number'] += 1
            dict_to_update['move_vals_list'].append(move_vals)

        values.update({
            'sale_invoice_vals': sale_invoice_vals,
            'purchase_invoice_vals': purchase_invoice_vals,
        })

    @api.model
    def _l10n_bg_saft_fill_payment_values(self, values):
        payment_vals = {
            'total_debit': 0.0,
            'total_credit': 0.0,
            'number': 0,
            'move_vals_list': [],
        }
        for move_vals in values['move_vals_list']:
            if not move_vals['statement_line_id']:
                continue
            move_vals.update({
                # Payment method '01' corresponds to cash,
                # '03' corresponds to non-cash money transfers,
                # '02' is for write off and miscellaneous transfers.
                'payment_method': '01' if move_vals['journal_type'] == 'cash' else
                                ('03' if move_vals['journal_type'] == 'bank' else '02'),
                'description': move_vals['line_vals_list'][0]['name'],
                'payment_line_vals_list': [],
            })

            for line_vals in move_vals['line_vals_list']:
                if line_vals['account_type'] in ('asset_cash', 'liability_credit_card'):
                    move_vals['payment_line_vals_list'].append(line_vals)
                    payment_vals['total_debit'] += line_vals['debit']
                    payment_vals['total_credit'] += line_vals['credit']

            payment_vals['number'] += 1
            payment_vals['move_vals_list'].append(move_vals)

        values['payment_vals'] = payment_vals

    def _check_cyrillic_name(self, name):
        return bool(re.search(r'[\u0400-\u04FF\u0500-\u052F]', name))

    @api.model
    def _l10n_bg_saft_prepare_report_values(self, report, options):

        values = self._saft_prepare_report_values(report, options)

        values['check_cyrillic_name'] = self._check_cyrillic_name

        self._l10n_bg_saft_check_header_values(values)

        self._l10n_bg_saft_update_partner_detail_map(values)

        self._l10n_bg_saft_check_saft_accounts(values)
        self._l10n_bg_saft_fill_saft_account_by_code(values)

        self._l10n_bg_saft_check_tax_values(values)
        self._l10n_bg_saft_fill_tax_values(values)

        self._l10n_bg_saft_fill_uom_values(values)
        self._l10n_bg_saft_check_uom_values(values)

        self._l10n_bg_saft_fill_product_values(values)

        self._l10n_bg_saft_fill_invoice_values(values)

        self._l10n_bg_saft_fill_payment_values(values)

        values.update({
            'xmlns': 'mf:nra:dgti:dxxxx:declaration:v1',
            'file_version': '1.02',
        })
        return values

    @api.model
    def l10n_bg_export_saft_to_xml(self, options):
        report = self.env['account.report'].browse(options['report_id'])
        values = self._l10n_bg_saft_prepare_report_values(report, options)
        return report._generate_file_data_with_error_check(
            options,
            self.env['ir.qweb']._render,
            {
                'values': values,
                'template': 'l10n_bg_saft.saft_template_inherit_l10n_bg_saft',
                'file_type': 'xml',
            },
            values['errors'],
        )

    def _saft_get_account_type(self, account_type):
        # OVERRIDE account_saft/models/account_general_ledger
        if self.env.company.account_fiscal_country_id.code != 'BG':
            return super()._saft_get_account_type(account_type)

        # BG saf-t account types have to be identified as follows:
        # Account type - "Active", "Passive", "Bifunctional"
        account_type_dict = {  # map between the account_types and the BG saf-t equivalent
            'asset_non_current': 'Active',
            'asset_fixed': 'Active',
            'asset_receivable': 'Active',
            'asset_cash': 'Active',
            'asset_current': 'Active',
            'asset_prepayments': 'Active',
            'equity': 'Passive',
            'equity_unaffected': 'Passive',
            'liability_payable': 'Passive',
            'liability_credit_card': 'Passive',
            'liability_current': 'Passive',
            'liability_non_current': 'Passive',
            'income': 'Passive',
            'income_other': 'Passive',
            'expense': 'Active',
            'expense_other': 'Active',
            'expense_depreciation': 'Active',
            'expense_direct_cost': 'Active',
            'off_balance': 'Bifunctional',
        }
        return account_type_dict[account_type]
