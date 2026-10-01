# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    agent_ids = fields.One2many("ai.agent", inverse_name="partner_id")

    def _store_im_status_fields(self, res):
        super()._store_im_status_fields(res)
        # sudo: ai.agent - knowing if a partner is an AI agent is acceptable
        res.many("agent_ids", [], sudo=True)
