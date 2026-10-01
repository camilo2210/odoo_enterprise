from odoo import fields, models


class ApplicantGetRefuseReason(models.TransientModel):
    _inherit = 'applicant.get.refuse.reason'

    res_ids = fields.Text('Related Document IDs', compute='_compute_res_ids')

    def _compute_res_ids(self):
        for wizard in self:
            wizard.res_ids = wizard.applicant_ids.ids
