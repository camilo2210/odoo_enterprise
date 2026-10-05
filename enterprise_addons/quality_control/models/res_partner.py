# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    quality_check_count = fields.Integer(
        compute='_compute_quality_rate', groups='quality.group_quality_user')
    quality_rate = fields.Float(
        compute='_compute_quality_rate', groups='quality.group_quality_user')

    def _compute_quality_rate(self):
        date_from = fields.Datetime.now() - relativedelta(years=1)
        quality_data = {
            partner: (quality_rate, quality_check_count)
            for partner, quality_rate, quality_check_count in self.env['quality.check']._read_group(
                [
                    ('partner_id', 'in', self.ids),
                    ('control_date', '>=', date_from),
                    ('picking_id.picking_type_id.code', '=', 'incoming'),
                    ('quality_state', '!=', 'none'),
                ],
                ['partner_id'],
                ['quality_rate:avg', '__count'],
            )
        }
        for partner in self:
            partner.quality_rate, partner.quality_check_count = quality_data.get(partner, (0.0, 0))

    def action_see_quality_rate(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('quality_control.quality_check_action_report')
        action['domain'] = [
            ('picking_id.picking_type_id.code', '=', 'incoming'),
            ('quality_state', '!=', 'none'),
        ]
        action['context'] = {
            'graph_measure': 'quality_rate',
            'pivot_measures': ['quality_rate'],
            'search_default_by_product': 1,
            'search_default_control_date_last_year': 1,
            'search_default_partner_id': self.id,
        }
        return action
