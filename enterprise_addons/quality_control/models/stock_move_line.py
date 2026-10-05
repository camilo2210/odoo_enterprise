# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    check_ids = fields.One2many('quality.check', 'move_line_id', 'Checks')
    check_state = fields.Selection([
        ('no_checks', 'No checks'),
        ('in_progress', 'Some checks to be done'),
        ('pass', 'All checks passed'),
        ('fail', 'Some checks failed')], compute="_compute_check_state")

    @api.depends('check_ids')
    def _compute_check_state(self):
        for line in self:
            if not line.check_ids:
                line.check_state = 'no_checks'
            elif line.check_ids.filtered(lambda check: check.quality_state == 'none'):
                line.check_state = 'in_progress'
            elif line.check_ids.filtered(lambda check: check.quality_state == 'fail'):
                line.check_state = "fail"
            else:
                line.check_state = "pass"

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        if self.env.context.get('no_checks'):
            # no checks for you
            return lines
        lines._filter_move_lines_applicable_for_quality_check()._create_check()
        return lines

    def write(self, vals):
        if self._create_quality_check_at_write(vals):
            self.filtered(lambda ml: ml.state != 'done' and not ml.sudo().check_ids)._create_check()
        if 'picking_id' in vals:
            self.check_ids.filtered(lambda qc: qc.point_id.measure_on == 'move_line').picking_id = vals['picking_id']
        return super().write(vals)

    def unlink(self):
        self.sudo()._unlink_quality_check()
        return super(StockMoveLine, self).unlink()

    def action_open_quality_check_wizard(self):
        return self.check_ids.action_open_quality_check_wizard()

    def _unlink_quality_check(self):
        self.check_ids.filtered(lambda qc: qc._check_to_unlink()).unlink()

    def _create_quality_check_at_write(self, vals):
        return vals.get('quantity')

    def _create_check(self):
        check_values_list = []
        quality_points_domain = self.env['quality.point']._get_domain(
            self.product_id, self.move_id.picking_type_id, measure_on='move_line')
        quality_points = self.env['quality.point'].sudo().search(quality_points_domain)
        quality_points_by_product_picking_type = {}

        product_ids_by_categ_id = {}
        if categ_ids := set(quality_points.product_category_ids.ids):
            categ_products = self.env['product.product'].search([
                ('categ_id', 'child_of', list(categ_ids)),
                ('id', 'in', self.product_id.ids),
            ])
            for product in categ_products:
                # parent_path contains the category itself and all its ancestors.
                for categ_id in map(int, product.categ_id.parent_path.split('/')[:-1]):
                    if categ_id in categ_ids:
                        product_ids_by_categ_id.setdefault(categ_id, []).append(product.id)

        for quality_point in quality_points:
            for product in quality_point.product_ids:
                for picking_type in quality_point.picking_type_ids:
                    quality_points_by_product_picking_type.setdefault(
                        (product, picking_type), set()).add(quality_point.id)
            for categ in quality_point.product_category_ids:
                categ_products = self.env['product.product'].browse(
                    product_ids_by_categ_id.get(categ.id, [])
                )
                for product in categ_products:
                    for picking_type in quality_point.picking_type_ids:
                        quality_points_by_product_picking_type.setdefault(
                            (product, picking_type), set()).add(quality_point.id)
            if not quality_point.product_ids and not quality_point.product_category_ids:
                for picking_type in quality_point.picking_type_ids:
                    quality_points_by_product_picking_type.setdefault(
                        (None, picking_type), set()).add(quality_point.id)

        quality_points_by_id = {
            quality_point.id: quality_point
            for quality_point in quality_points
        }
        for ml in self:
            quality_points_product = quality_points_by_product_picking_type.get((ml.product_id, ml.move_id.picking_type_id), set())
            quality_points_all_products = ml._get_quality_points_all_products(quality_points_by_product_picking_type)
            quality_point_ids = quality_points_product | quality_points_all_products
            for quality_point_id in quality_point_ids:
                quality_point = quality_points_by_id[quality_point_id]
                if quality_point.check_execute_now():
                    check_values = ml._get_check_values(quality_point)
                    check_values_list.append(check_values)
        if check_values_list:
            self.env['quality.check'].sudo().create(check_values_list)

    def _filter_move_lines_applicable_for_quality_check(self):
        return self.filtered(lambda line: line.quantity != 0)

    def _get_check_values(self, quality_point):
        return {
            'point_id': quality_point.id,
            'measure_on': quality_point.measure_on,
            'team_id': quality_point.team_id.id,
            'product_id': self.product_id.id,
            'picking_id': self.picking_id.id,
            'batch_id': self.picking_id.batch_id.id,
            'move_line_id': self.id,
            'lot_name': self.lot_name,
            'company_id': self.company_id.id,
        }

    def _get_quality_points_all_products(self, quality_points_by_product_picking_type):
        return quality_points_by_product_picking_type.get((None, self.move_id.picking_type_id), set())

    def _is_checkable(self, check_picked=False):
        self.ensure_one()
        if self.uom_id.is_zero(self.quantity):
            return False
        if check_picked:
            return self.picked
        return True
