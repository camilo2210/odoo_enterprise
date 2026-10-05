from odoo import api, fields, models
from odoo.exceptions import ValidationError


class QualityPoint(models.Model):
    _inherit = 'quality.point'

    l10n_tr_show_unit_count = fields.Boolean(compute='_compute_l10n_tr_show_unit_count')

    @api.depends('company_id.country_id', 'picking_type_ids.code')
    def _compute_l10n_tr_show_unit_count(self):
        for point in self:
            point.l10n_tr_show_unit_count = (
                point.company_id.country_id.code == 'TR'
                and all(picking_type.code == 'incoming' for picking_type in point.picking_type_ids)
            )

    @api.onchange('test_type_id')
    def _onchange_l10n_tr_unit_count_measure_on(self):
        if self.test_type == 'unit_count':
            self.measure_on = 'operation'

    @api.constrains('test_type_id', 'picking_type_ids', 'measure_on', 'company_id')
    def _check_l10n_tr_unit_count(self):
        for point in self.filtered(lambda p: p.test_type == 'unit_count'):
            if point.company_id.country_id.code != 'TR':
                raise ValidationError(self.env._(
                    "%(point)s is a Unit Count control point, which is only available for Turkish companies.",
                    point=point.display_name,
                ))
            if point.measure_on != 'operation':
                raise ValidationError(self.env._(
                    "%(point)s is a Unit Count control point, so it must be controlled per Operation.",
                    point=point.display_name,
                ))
            if invalid_types := point.picking_type_ids.filtered(lambda t: t.code != 'incoming'):
                raise ValidationError(self.env._(
                    "%(point)s is a Unit Count control point, so it cannot be used on %(operations)s. Only receipt operation types are allowed.",
                    point=point.display_name,
                    operations=', '.join(invalid_types.mapped('display_name')),
                ))
