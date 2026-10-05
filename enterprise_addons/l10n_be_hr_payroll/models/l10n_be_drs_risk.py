# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import UserError


class L10nBeDrsRisk(models.Model):
    _name = 'l10n.be.drs.risk'
    _description = 'DRS - Risk Identification'
    _rec_name = 'name'

    name = fields.Char(string="Label", required=True, help="Precise name of the risk according to NSSO Appendix 12.")

    sector = fields.Selection([
        ('work_accident', 'Work Accidents (Fedris)'),
        ('unemployment', 'Unemployment (ONEM/RVA)'),
        ('compensation', 'Benefits & Compensation (INAMI/RIZIV)'),
    ], string="Sector", required=True)

    identification = fields.Char(string="Identification", required=True, help="E.g., WECH001, ZIMA001")
    code = fields.Char(string="Code", required=True, help="3-digit code (e.g., 001)")
    scenario = fields.Char(string="Scenario", required=True)

    date_start = fields.Date(string="Valid From", required=True)
    date_end = fields.Date(string="Valid Until")

    _unique_identification_code = models.Constraint(
        'UNIQUE(identification, code)',
        'The combination of Identification and Code must be strictly unique according to the CBSS nomenclature.'
    )

    @api.ondelete(at_uninstall=False)
    def _unlink_prevent_deletion(self):
        raise UserError(self.env._(
            "You are not allowed to delete a DRS Risk nomenclature record."
            "If this scenario is no longer valid according to the NSSO, please adjust the 'Valid Until' field to expire it instead."
        ))

    @api.depends('identification', 'code', 'name')
    def _compute_display_name(self):
        """Displays the complete code to facilitate searching by the HR operator."""
        for record in self:
            record.display_name = f"[{record.identification}.{record.code}] {record.name}"
