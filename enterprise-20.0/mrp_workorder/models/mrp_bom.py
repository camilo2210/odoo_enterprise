# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class MrpBom(models.Model):
    _name = 'mrp.bom'
    _inherit = ['mail.activity.mixin', 'mrp.bom']

    quality_point_count = fields.Integer('Instructions Count', compute='_compute_quality_point_count')

    @api.depends('operation_ids.quality_point_ids')
    def _compute_quality_point_count(self):
        for bom in self:
            bom.quality_point_count = sum(bom.operation_ids.mapped('quality_point_count'))

    def write(self, vals):
        res = super().write(vals)
        if 'product_id' in vals or 'product_tmpl_id' in vals:
            self.operation_ids.quality_point_ids._change_product_ids_for_bom(self)
        return res

    def copy(self, default=None):
        new_boms = super().copy(default)
        for old_bom, new_bom in zip(self, new_boms):
            if points_with_bom_line := new_bom.operation_ids.quality_point_ids.filtered('bom_line_id'):
                bom_line_mapping = {}
                for original, copied in zip(old_bom.bom_line_ids, new_bom.bom_line_ids.sorted('sequence')):
                    bom_line_mapping[original.id] = copied.id
                for point in points_with_bom_line:
                    point.bom_line_id = bom_line_mapping.get(point.bom_line_id.id)
            if points_with_byproduct := new_bom.operation_ids.quality_point_ids.filtered('byproduct_id'):
                byproduct_mapping = {}
                for original, copied in zip(old_bom.byproduct_ids, new_bom.byproduct_ids.sorted('sequence')):
                    byproduct_mapping[original.id] = copied.id
                for point in points_with_byproduct:
                    point.byproduct_id = byproduct_mapping.get(point.byproduct_id.id)
        return new_boms


class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    @api.depends_context('formatted_display_name')
    def _compute_display_name(self):
        super()._compute_display_name()
        if self.env.context.get('formatted_display_name'):
            for line in self:
                line.display_name = f"{line.product_id.name}\t--{line.product_qty} {line.uom_id.name}--"

    def write(self, vals):
        if 'product_id' in vals:
            product = self.env['product.product'].browse(vals['product_id'])
            if product.is_kits:
                self.bom_id.operation_ids.quality_point_ids.filtered(lambda qp: qp.bom_line_id in self).bom_line_id = False
        return super().write(vals)


class MrpBomByProduct(models.Model):
    _inherit = 'mrp.bom.byproduct'

    @api.depends_context('formatted_display_name')
    def _compute_display_name(self):
        super()._compute_display_name()
        if self.env.context.get('formatted_display_name'):
            for line in self:
                line.display_name = f"{line.product_id.name}\t--{line.product_qty} {line.uom_id.name}--"
