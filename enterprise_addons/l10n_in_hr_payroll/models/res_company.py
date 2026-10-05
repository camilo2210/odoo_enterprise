# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models

L10N_IN_DEDUCTOR_TYPE_SELECTION = [
    ('A', "Central Government"),
    ('S', "State Government"),
    ('D', "Statutory body (Central Govt.)"),
    ('E', "Statutory body (State Govt.)"),
    ('G', "Autonomous body (Central Govt.)"),
    ('H', "Autonomous body (State Govt.)"),
    ('L', "Local Authority (Central Govt.)"),
    ('N', "Local Authority (State Govt.)"),
    ('K', "Company"),
    ('M', "Branch / Division of Company"),
    ('P', "Association of Person (AOP)"),
    ('T', "Association of Person (Trust)"),
    ('J', "Artificial Juridical Person"),
    ('B', "Body of Individuals"),
    ('Q', "Individual/HUF"),
    ('F', "Firm"),
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_in_deductor_tan = fields.Char(string="TAN No.", help="10-character Tax Deduction and Collection Account Number.")
    l10n_in_deductor_pan = fields.Char(string="PAN No.", help="10-character Permanent Account Number, or PANNOTREQD if not required.")
    l10n_in_deductor_type = fields.Selection(
        selection=L10N_IN_DEDUCTOR_TYPE_SELECTION,
        string="Deductor Type",
        help="Deductor category code as per the Indian TDS return file format.",
    )
    l10n_in_responsible_person_id = fields.Many2one(
        'hr.employee',
        string="Responsible Person",
        help="Person responsible for deducting tax.",
        domain=[('private_country_id.code', '=', 'IN')],
    )
    l10n_in_epf_employer_id = fields.Char(string="EPF Employer ID",
        help="Region code: 2 uppercase letters (e.g., 'GJ' for Gujarat)\nOffice code: 3 uppercase letters\
        (e.g., 'AHM' for Ahmedabad)\nEstablishment code: 7 digits (e.g., '1234567')\nExtension code:\
        3 digits (e.g., '000')\nFormat: XX/XXX/1234567/000")
    l10n_in_esic_ip_number = fields.Char(string="ESIC IP Number",
        help="Code of 17 digits.\n The Identification number is assigned to the company if registered under the\
        Indian provisions of the Employee\'s State Insurance (ESI) Act.")
    l10n_in_pt_number = fields.Char(string="PT Number",
        help="The PTN digit number with the first two digits indicating the State.")
    l10n_in_provident_fund = fields.Boolean(string="Provident Fund",
        help="Check this box if the company is required to comply with the Indian provisions of the\
        Employee's Provident Fund (EPF) Act.")
    l10n_in_esic = fields.Boolean(string="Employee's State Insurance",
        help="Check this box if the company is required to comply with the Indian provisions of the\
        Employee's State Insurance (ESI) Act.")
    l10n_in_pt = fields.Boolean(string="Professional Tax(PT)")
    l10n_in_labour_welfare = fields.Boolean(string="Labour Welfare Fund", default=True,
        help="Check this box if the company is required to comply with the Indian provisions of the Labour\
        Welfare Fund (LWF) Act.")
    l10n_in_labour_identification_number = fields.Char(string="Labour Identification Number",
        help="The Labour Welfare Fund ID is assigned to the company if registered under the\
        Indian provisions of the Labour Welfare Fund (LWF) Act.")
    l10n_in_corporate_identification_number = fields.Char(string="Corporate Identification Number")
    _check_l10n_in_epf_employer_id = models.Constraint(
        "CHECK (l10n_in_epf_employer_id ~ '^[A-Z]{2}/[A-Z]{3}/[0-9]{7}/[0-9]{3}$')",
        "EPF Number format must be: XX/XXX/1234567/000"
    )
    _check_l10n_in_esic_ip_number = models.Constraint(
        "CHECK(l10n_in_esic_ip_number ~ '^[0-9]{17}$')",
        "ESIC IP Number must be exactly 17 characters.",
    )
    _check_l10n_in_deductor_tan = models.Constraint(
        "CHECK(l10n_in_deductor_tan ~ '^[A-Z]{4}[0-9]{5}[A-Z]$')",
        "TAN must be a valid 10-character TAN, for example ABCD12345E.",
    )
    _check_l10n_in_deductor_pan = models.Constraint(
        "CHECK(l10n_in_deductor_pan ~ '^([A-Z]{5}[0-9]{4}[A-Z])$')",
        'PAN must be a valid 10-character PAN.',
    )

    def _prepare_resource_calendar_values(self):
        """
        Override to set the default calendar to
        start at 10:00 and end at 19:00 for
        Indian companies
        """
        vals = super()._prepare_resource_calendar_values()
        if self.country_id.code == 'IN':
            vals.update({
                'name': self.env._('40 hours/week - %s', self.name),
                'full_time_required_hours': 40,
                'attendance_ids': [
                    (0, 0, {'dayofweek': '0', 'duration_hours': 8, 'hour_from': 0, 'hour_to': 0}),
                    (0, 0, {'dayofweek': '1', 'duration_hours': 8, 'hour_from': 0, 'hour_to': 0}),
                    (0, 0, {'dayofweek': '2', 'duration_hours': 8, 'hour_from': 0, 'hour_to': 0}),
                    (0, 0, {'dayofweek': '3', 'duration_hours': 8, 'hour_from': 0, 'hour_to': 0}),
                    (0, 0, {'dayofweek': '4', 'duration_hours': 8, 'hour_from': 0, 'hour_to': 0}),
                ],
            })
        return vals
