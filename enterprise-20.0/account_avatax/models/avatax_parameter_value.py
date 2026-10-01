from odoo import api, fields, models


class AvataxParameterValue(models.Model):
    _name = 'avatax.parameter.value'
    _rec_name = 'parameter_id'
    _description = "Avatax Parameter Value"

    parameter_id = fields.Many2one('avatax.parameter', required=True, index=True, ondelete='restrict')
    data_type = fields.Selection(related='parameter_id.data_type')
    parameter_description = fields.Text(related='parameter_id.description')
    measurement_type = fields.Char(related='parameter_id.measurement_type')
    value_boolean = fields.Boolean()
    value_float = fields.Float()
    value_char = fields.Char()  # Date parameters also use value_char because the expected format varies per parameter.
    value_selection_id = fields.Many2one(
        'avatax.parameter.selection',
        domain="[('parameter_id', '=', parameter_id)]",
        ondelete='restrict',
    )
    value = fields.Char(compute='_compute_value')
    avatax_uom_id = fields.Many2one(
        'avatax.uom',
        string='Avatax UOM',
        domain="[('measurement_type', '=', measurement_type)]",
    )
    product_id = fields.Many2one('product.product', required=True, index=True, ondelete='cascade')

    _parameter_product_uniq = models.Constraint(
        'UNIQUE (parameter_id, product_id)',
        "The product already has a value for this parameter.",
    )

    @api.onchange('avatax_uom_id')
    def _onchange_avatax_uom_id(self):
        """ When the user puts in a volume or weight parameter, auto-fill it based on the weight/volume field. """
        if self.data_type != 'NumericMeasured' or not self.avatax_uom_id:
            return

        product = self.product_id or self.env['product.product'].browse(self.env.context.get('default_product_id'))
        if self.measurement_type == 'Mass':
            product_quantity = product.weight
            product_uom = self.env['product.template']._get_weight_uom_id_from_ir_config_parameter()
        elif self.measurement_type == 'Volume':
            product_quantity = product.volume
            product_uom = self.env['product.template']._get_volume_uom_id_from_ir_config_parameter()
        else:
            return

        if not product_quantity:
            return

        odoo_uom = self.avatax_uom_id._get_odoo_uom()
        if not odoo_uom:
            return

        self.value_float = product_uom._compute_quantity(product_quantity, odoo_uom)

    @api.depends('parameter_id.name', 'data_type', 'value', 'value_boolean', 'avatax_uom_id.name')
    def _compute_display_name(self):
        for record in self:
            if record.data_type == 'Boolean':
                value = record.env._("Yes") if record.value_boolean else record.env._("No")
            elif record.data_type in ('NumericMeasured', 'NumericCurrency'):
                value = record.value.rstrip('0').rstrip('.')
                if record.avatax_uom_id:
                    value = f"{value} {record.avatax_uom_id.name}"
            else:
                value = record.value
            record.display_name = f"{record.parameter_id.name}: {value}"

    @api.depends('data_type', 'value_boolean', 'value_float', 'value_char', 'value_selection_id')
    def _compute_value(self):
        """ Serialize to the string sent to Avalara. """
        for record in self:
            match record.data_type:
                case 'Boolean':
                    record.value = 'true' if record.value_boolean else 'false'
                case 'NumericMeasured' | 'NumericCurrency':
                    record.value = f'{record.value_float:f}'
                case 'Enumeration':
                    record.value = record.value_selection_id.name or ''
                case 'String' | 'Date':
                    record.value = record.value_char or ''
                case _:
                    record.value = ''
