# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _prepare_move_for_asset_depreciation(
        self, *, asset_variant, amount, depreciation_beginning_date, date, asset_number_days, **kwargs,
    ):
        # Overridden in order to link the depreciation entries with the vehicle_id
        move_vals = super()._prepare_move_for_asset_depreciation(
            asset_variant=asset_variant,
            amount=amount,
            depreciation_beginning_date=depreciation_beginning_date,
            date=date,
            asset_number_days=asset_number_days,
            **kwargs,
        )
        if asset_variant.vehicle_id:
            for _command, _id, line_vals in move_vals['line_ids']:
                line_vals['vehicle_id'] = asset_variant.vehicle_id.id
        return move_vals
