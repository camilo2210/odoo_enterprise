import re
from odoo import api, fields, models

FR_STREET_PATTERN_START = re.compile(r'^(?P<number>\d+)\s*[-/]?\s*(?P<number_suffix>[A-Za-z]+)?\s*(?P<rest>.*)$')
FR_STREET_PATTERN_END = re.compile(r'^(?P<rest>.*\D)\s*(?P<number>\d+)\s*[-/]?\s*(?P<number_suffix>[A-Za-z]+)?$')

REPETITION_INDICATOR_MAP = {
    'B': 'B',
    'BIS': 'B',
    'T': 'T',
    'TER': 'T',
    'Q': 'Q',
    'QUATER': 'Q',
    'C': 'C',
}


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # These fields are required for the DAS2 report.
    l10n_fr_profession_id = fields.Many2one(
        comodel_name='l10n_fr.res.partner.profession',
        string="DAS2 - Profession",
        help="DAS2 - Profession of the partner",
    )
    birth_date = fields.Date(
        string="Birth Date",
        help="Birth Date of the partner (Required for DAS2 beneficiaries that are not French residents but live in the EU)",
    )

    @api.model
    def _parse_address_parts(self, street_number_suffix_raw, street_rest, is_start=True):
        """ Parse address parts according to French conventions.
            :param street_number_suffix_raw: The raw street number repetition indicator.
            :param street_rest: The rest of the street address.
            :param is_start: Whether the street number is at the start of the address.
        """
        raw = (street_number_suffix_raw or "").strip()
        rest = (street_rest or "").strip()

        key = re.sub(r'[.,;:]+$', '', raw).strip().upper()  # normalizing the key by removing trailing punctuation and converting to uppercase
        if key in REPETITION_INDICATOR_MAP:
            return REPETITION_INDICATOR_MAP[key], rest

        street = f"{raw} {rest}".strip() if is_start else f"{rest} {raw}".strip()
        return "", street

    @api.model
    def _split_french_street(self, street):
        street = (street or '').strip()
        if not street:
            return False, False, False

        for pattern, is_start in ((FR_STREET_PATTERN_START, True), (FR_STREET_PATTERN_END, False)):
            match = pattern.match(street)
            if not match:
                continue

            street_number = match.group('number')
            number_suffix, voie = self._parse_address_parts(
                match.group('number_suffix'),
                (match.group('rest') or '').strip(),
                is_start=is_start,
            )
            if street_number:
                return (voie or street, street_number, number_suffix or False)

        return street, False, False

    def _compute_street_data(self):
        """Overrides base_address_extended to adhere to French specificities."""
        irrelevant_partners = self.env['res.partner']

        for partner in self:
            if not partner.l10n_fr_is_french:
                irrelevant_partners |= partner
                continue

            street_name, street_number, street_number2 = self._split_french_street(partner.street)
            partner.update({
                'street_name': street_name,
                'street_number': street_number,
                'street_number2': street_number2,
            })

        return super(ResPartner, irrelevant_partners)._compute_street_data()
