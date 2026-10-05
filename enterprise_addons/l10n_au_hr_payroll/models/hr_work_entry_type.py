# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrWorkEntryType(models.Model):
    _inherit = 'hr.work.entry.type'

    l10n_au_is_ote = fields.Boolean(
        string="Is OTE", tracking=True,
        help="This work entry type will be subjected to the superannuation guarantee %.")
    l10n_au_work_stp_code = fields.Selection(
        selection=[
            ("G", "Gross"),
            ("T", "Overtime"),
            ("O", "Other Paid Leave"),
            ("P", "Paid Parental Leave"),
            ("W", "Workers Compensation"),
            ("A", "Ancillary and Defence Leave"),
        ],
        string="STP Code",
        tracking=True,
        help='This tells Odoo how to report the time spent in this category to the ATO. Under STP Phase 2, income must be "disaggregated" into specific buckets rather than reported as one lump sum. We do not recommend changing the value of this field if it was already set by default.')
    l10n_au_work_entry_type = fields.Selection(
        selection=[
            ("annual", "General Leave"),
            ("long_service", "Long Service"),
            ("personal", "Unpaid at Termination"),
        ],
        default="personal",
        required=True,
        tracking=True,
        string="Unused Leave Type",
        help="""This will affect the employee's leave payout upon termination.
        - General: any type of leave paid at termination that is not long service leave.
        - Long service: for long service leave paid at termination.
        - Unpaid at termination"""
    )

    @api.model
    def _get_critical_fields(self):
        return super()._get_critical_fields() + ['l10n_au_is_ote', 'l10n_au_work_stp_code', 'l10n_au_work_entry_type']

    def _get_data_files_to_update(self):
        # Note: file order should be maintained
        return super()._get_data_files_to_update() + [(
            'l10n_au_hr_payroll', [
                'data/hr_work_entry_type_data.xml',
            ])]
