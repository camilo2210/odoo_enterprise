from stdnum.cz.dic import compact

from odoo import _, fields
from odoo.tools import date_utils
from odoo.exceptions import RedirectWarning


def get_eu_country_codes(env, options):
    rslt = env.ref('base.europe').country_ids.mapped('code')

    # GB left the EU on January 1st 2021. But before this date, it's still to be considered as a EC country
    if fields.Date.from_string(options['date']['date_from']) < fields.Date.from_string('2021-01-01'):
        rslt.append('GB')
    return rslt


def validate_czech_company_fields(sender_company):
    if not sender_company.l10n_cz_tax_office_id or not sender_company.vat:
        raise RedirectWarning(
            message=_("Please first set a tax office and tax ID on your company."),
            action=sender_company._get_records_action(name=_("Company: %s", sender_company.name), target='new'),
            button_text=_("Go to Company"),
        )


def get_veta_d_vals(report, options, sender_company):
    report_to_form_mapping = {
        'l10n_cz_reports.control_statement_report': {'document': "KH1", 'control_report_form': "B"},
        'l10n_cz_reports.vies_summary_report': {'document': "SHV", 'vies_report_form': "N"},
        'l10n_cz.l10n_cz_vat_declaration': {
            'document': "DP3",
            'vat_report_form': "B",
            'vat_report_submitter_type': "P",
            'vat_report_economic_activity_code': sender_company.l10n_cz_economic_activity_code,
        },
    }

    date_from = fields.Date.from_string(options['date']['date_from'])
    period_type = options['date']['period_type']
    report_xml_id = report.get_external_id().get(report.id)
    return {
        'quarter': date_utils.get_quarter_number(date_from) if period_type == 'quarter' else None,
        'month': date_from.month if period_type == 'month' else None,
        'year': date_from.year,
        'date_issue': fields.Date.context_today(report).strftime("%d.%m.%Y"),
        **report_to_form_mapping.get(report_xml_id),
    }


def get_veta_p_vals(report, sender_company, contact_partner):
    def safe_truncate_str(value, max_length):
        """
        Allows limiting the length of `value` if it is a string. If empty or not a string, return None.
        This allows skipping otherwise empty tags in the export.
        """
        if isinstance(value, str) and value:
            return value[:max_length]
        return None

    report_to_form_mapping = {
        'l10n_cz_reports.control_statement_report': {'email': sender_company.email},
        'l10n_cz.l10n_cz_vat_declaration': {'email': sender_company.email},
    }

    report_xml_id = report.get_external_id().get(report.id)
    values = {
        'street': safe_truncate_str(sender_company.partner_id.street_name, 38),
        'street_number': safe_truncate_str(sender_company.partner_id.street_number, 4),
        'building_complement': safe_truncate_str(sender_company.partner_id.street_number2, 6),
        'postal_code': sender_company.partner_id.zip,
        'city': sender_company.partner_id.city,
        # Country is an optional header field, filled based on naz_zeme_c25 in https://adisspr.mfcr.cz/pmd/dokumentace/ciselniky/ukazka/zeme
        # To avoid mapping every country name for an optional field for the report-filling company, only CZ is translated
        'country': 'ČESKÁ REPUBLIKA' if sender_company.partner_id.country_id.code == 'CZ' else None,
        'workplace_code': sender_company.l10n_cz_tax_office_id.workplace_code,
        'office_code': sender_company.l10n_cz_tax_office_id.code,
        'vat': compact(sender_company.vat),
        'company_type': "F" if not sender_company.partner_id.is_company else "P",
        'company_name': sender_company.name,
        'contact_first_name': safe_truncate_str(contact_partner.name.split()[0], 20),
        'contact_surname': safe_truncate_str(' '.join(contact_partner.name.split()[1:]), 36),
        'contact_phone': contact_partner.phone.replace('-', '')[:14] if contact_partner.phone else None,
        **report_to_form_mapping.get(report_xml_id, {}),
    }
    if sender_company.l10n_cz_person_authorized and values['company_type'] == 'P':
        values |= {
            'authorized_person_first_name': (sender_company.l10n_cz_person_authorized.name or '').split()[0][:20],
            'authorized_person_surname': ' '.join((sender_company.l10n_cz_person_authorized.name or '').split()[1:])[:36],
            'authorized_person_relationship': safe_truncate_str(sender_company.l10n_cz_relationship_person_authorized, 40),
        }
    return values
