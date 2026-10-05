from odoo import api, fields, models


class EsgEmissionFactorLine(models.Model):
    _name = 'esg.emission.factor.line'
    _description = 'Emission Factor Line'
    _inherit = ['mail.track.mixin']

    esg_emission_factor_id = fields.Many2one('esg.emission.factor', string='Emission Factor', index=True)
    activity_type_id = fields.Many2one('esg.activity.type', string='Activity Type', tracking=True)
    gas_id = fields.Many2one('esg.gas', required=True, index=True, tracking=True)
    quantity = fields.Float(string='kg', default=1.0, required=True, tracking=True, digits=(16, 8))  # Fixing the digits for a correct display in tracking values.
    esg_emissions_value = fields.Float(string='Emissions (kgCO₂e)', compute='_compute_esg_emissions_value', store=True, tracking=True, digits=(1, 8))

    @api.depends('quantity', 'gas_id.global_warming_potential')
    def _compute_esg_emissions_value(self):
        for emission in self:
            emission.esg_emissions_value = emission.quantity * emission.gas_id.global_warming_potential

    @api.depends('gas_id')
    def _compute_display_name(self):
        for gas_line in self:
            gas_line.display_name = self.env._(
                '%(gas_name)s (%(quantity)s kg)',
                gas_name=gas_line.gas_id.name,
                quantity=gas_line.quantity,
            )

    def write(self, vals):
        """Track field changes and log them to the linked emission factor."""
        # Log changes to gas lines on the emission factor.
        tracked_field_names = {fname for fname in self._track_get_fields() if fname in vals}
        if tracked_field_names:
            for gas_line in self:
                gas_line.esg_emission_factor_id._track_record(
                    gas_line, tracked_field_names,
                    body=self.env._(
                        "Updated values for %(gas_name)s (%(activity_type_name)s)",
                        gas_name=gas_line.gas_id.name,
                        activity_type_name=gas_line.activity_type_id.name or self.env._("No activity type"),
                    ),
                )

        return super().write(vals)
