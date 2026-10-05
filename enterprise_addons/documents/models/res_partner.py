# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields
from odoo.fields import Domain


class ResPartner(models.Model):
    _inherit = "res.partner"

    document_ids = fields.One2many('documents.document', 'partner_id', string='Documents')
    document_count = fields.Integer('Document Count', compute='_compute_document_count')

    def _compute_document_count(self):
        document_data = self.env['documents.document']._read_group(
            domain=self._get_documents_domain(),
            groupby=['partner_id'], aggregates=['__count']
        )
        self_ids = set(self._ids)
        self.document_count = 0
        for partner, count in document_data:
            while partner:
                if partner.id in self_ids:
                    partner.document_count += count
                partner = partner.parent_id

    def _get_documents_domain(self):
        return Domain('partner_id', 'child_of', self.ids)

    def action_see_documents(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('documents.document_action_preference')
        return action | {
            'domain': self._get_documents_domain(),
            'context': {
                'default_partner_id': self.id,
                'searchpanel_default_user_folder_id': False,
            },
        }

    def action_create_members_to_invite(self):
        return {
            'res_model': 'res.partner',
            'target': 'new',
            'type': 'ir.actions.act_window',
            'view_id': self.env.ref('base.view_partner_simple_form').id,
            'view_mode': 'form',
        }
