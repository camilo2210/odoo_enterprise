# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountAsset(models.Model):
    _inherit = 'account.asset'

    vehicle_id = fields.Many2one('fleet.vehicle', compute='_compute_vehicle_id', readonly=False, store=True)
    is_vehicle = fields.Boolean(related='account_asset_id.is_vehicle_account')

    @api.depends('original_move_line_ids')
    def _compute_vehicle_id(self):
        for asset in self.filtered(lambda a: a.state == 'draft'):
            if len(asset.original_move_line_ids.vehicle_id) > 1:
                raise UserError(_("All the lines should be from the same vehicle"))
            asset.vehicle_id = asset.original_move_line_ids.vehicle_id

    def action_open_vehicle(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.vehicle',
            'res_id': self.vehicle_id.id,
            'view_ids': [(False, 'form')],
            'view_mode': 'form',
        }

    @api.model_create_multi
    def create(self, vals_list):
        assets = super().create(vals_list)
        for asset in assets:
            if asset.vehicle_id and not asset.vehicle_id.net_car_value:
                asset.vehicle_id.net_car_value = asset.original_value
        return assets
