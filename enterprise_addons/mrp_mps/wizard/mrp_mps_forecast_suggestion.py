from odoo import api, Command, fields, models, _
from odoo.exceptions import ValidationError


class MrpMpsForecastSuggestion(models.TransientModel):
    _name = 'mrp.mps.forecast.suggestion'
    _description = "Forecast Demand Suggestion"

    mrp_mps_ids = fields.Many2many('mrp.production.schedule')
    product_id = fields.Many2one('product.product', compute='_compute_product_id')
    period = fields.Integer(string='Period')
    based_on = fields.Selection(
        [('actual_demand', 'Actual Demand'),
         ('last_year', 'Last Year'),
         ('30_days', 'Last 30 Days'),
         ('three_months', 'Last 3 Months'),
         ('one_year', 'Last 12 Months'),
        ]
        , required=True, default='last_year', string='Based on', readonly=False)
    percent_factor = fields.Integer(default=100, required=True)
    quantity = fields.Float(compute='_compute_suggestion_fields', digits='Product Unit')
    quantity_before_scale = fields.Float(compute='_compute_suggestion_fields', digits='Product Unit')

    @api.depends('mrp_mps_ids')
    def _compute_product_id(self):
        for wizard in self:
            wizard.product_id = wizard.mrp_mps_ids.product_id if len(wizard.mrp_mps_ids) == 1 else False

    def action_open_suggest_forecasted_form_view(self, mps_ids):
        context = dict(self.env.context)
        context['default_mrp_mps_ids'] = [Command.set(mps_ids)]
        context['default_period'] = 1
        context['default_based_on'] = 'actual_demand'
        return {
            'type': 'ir.actions.act_window',
            'name': _("Suggest Forecasted Demand"),
            'target': 'new',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'res_id': False,
            'view_id': self.env.ref('mrp_mps.mrp_mps_forecast_suggestion_form_view').id,
            'res_model': 'mrp.mps.forecast.suggestion',
            'context': context,
        }

    @api.constrains('percent_factor')
    def _check_percent_factor_gte_0(self):
        if self.percent_factor < 0:
            raise ValidationError(_("Percent factor cannot be less than zero."))

    @api.depends('period', 'based_on', 'percent_factor')
    def _compute_suggestion_fields(self):
        for wizard in self:
            wizard.quantity_before_scale = False
            wizard.quantity = False
            if len(wizard.mrp_mps_ids) != 1:
                continue

            period_index = 0
            period_scale = wizard.env.context.get('period_scale')
            qty_before_scale = 0
            mps = wizard.mrp_mps_ids

            if wizard.period:
                period_index = wizard.period - 1

            if wizard.period or wizard.based_on in ['30_days', 'three_months', 'one_year']:
                suggestion_quantities_by_mps = wizard._get_suggestion_quantities(period_scale=period_scale)
                qty_before_scale = suggestion_quantities_by_mps[mps.id][period_index]

            wizard.quantity_before_scale = mps.uom_id.round(qty_before_scale, rounding_method='UP')
            wizard.quantity = mps.uom_id.round(qty_before_scale * (wizard.percent_factor / 100), rounding_method='UP')

    def _get_suggestion_quantities(self, period_scale=False):
        if self.based_on in ['last_year', 'actual_demand']:
            return self._get_suggestion_quantities_for_period_type(period_scale=period_scale)
        else:
            return self._get_suggestion_quantities_for_period_length(period_scale=period_scale)

    def _get_suggestion_quantities_for_period_type(self, period_scale=False):
        """
        Return a dict of MPS ids and their suggestion demand quantities for the matched period of the selected type.
        """
        suggestion_quantities_by_mps = {}
        years = 0 if self.based_on == 'actual_demand' else 1
        for company, mps_records in self.mrp_mps_ids.grouped('company_id').items():
            date_range = company._get_date_range(years=years, force_period=period_scale)
            outgoing_qty, outgoing_qty_done, __, __ = mps_records._get_outgoing_qty(date_range)

            for mps in mps_records:
                suggestion_quantities = []
                for date in date_range:
                    period_qty = 0
                    key = (date, mps.product_id, mps.warehouse_id)
                    period_qty += outgoing_qty_done.get(key, 0.0)

                    if self.based_on == 'actual_demand':
                        period_qty += outgoing_qty.get(key, 0.0)

                    suggestion_quantities.append(period_qty)
                suggestion_quantities_by_mps[mps.id] = suggestion_quantities

        return suggestion_quantities_by_mps

    def _get_suggestion_quantities_for_period_length(self, period_scale=False):
        """
        Return a dict of MPS ids and their suggestion demand quantities representing a ratio between
        the length of the period of the selected type and the length of the demand period.
        """
        if period_scale == 'year':
            multiplier_monthly_demand = 12
        elif period_scale == 'month':
            multiplier_monthly_demand = 1
        elif period_scale == 'week':
            multiplier_monthly_demand = 7 / (365.25 / 12)
        else:
            multiplier_monthly_demand = 1 / (365.25 / 12)

        suggestion_quantities_by_mps = {}
        for company, mps_records in self.mrp_mps_ids.grouped('company_id').items():
            period_count = company['manufacturing_period_to_display_%s' % period_scale]
            for mps in mps_records:
                context = {
                    'suggest_based_on': self.based_on,
                    'warehouse_id': mps.warehouse_id.id,
                }
                product = mps.product_id.with_context(context)
                qty = product.monthly_demand * multiplier_monthly_demand
                suggestion_quantities_by_mps[mps.id] = [qty] * period_count
        return suggestion_quantities_by_mps

    def apply_forecast_quantity_suggestion(self):
        self.ensure_one()
        period_scale = self.env.context.get('period_scale')

        suggestion_quantities_by_mps = self._get_suggestion_quantities(period_scale=period_scale)
        for company, mps_records in self.mrp_mps_ids.grouped('company_id').items():
            for mps in mps_records:
                suggestion_quantities = suggestion_quantities_by_mps[mps.id]
                if self.period:
                    period_index = self.period - 1
                    quantity_to_suggest = mps.uom_id.round(suggestion_quantities[period_index] * (self.percent_factor / 100), rounding_method='UP')
                    mps.set_forecast_qty(period_index, quantity_to_suggest, period_scale=period_scale)
                else:
                    for i in range(company['manufacturing_period_to_display_%s' % period_scale]):
                        quantity_to_suggest = suggestion_quantities[i]
                        quantity_to_suggest = mps.uom_id.round(quantity_to_suggest * (self.percent_factor / 100), rounding_method='UP')
                        mps.set_forecast_qty(i, quantity_to_suggest, period_scale=period_scale)
