# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.misc import OrderedSet


class StockPicking(models.Model):
    _inherit = "stock.picking"

    check_ids = fields.One2many('quality.check', 'picking_id', 'Checks')
    quality_check_todo = fields.Boolean('Pending checks', compute='_compute_check', search='_search_quality_check_todo')
    quality_check_fail = fields.Boolean(compute='_compute_check')
    quality_alert_ids = fields.One2many('quality.alert', 'picking_id', 'Alerts')
    quality_alert_count = fields.Integer(compute='_compute_quality_alert_count')

    @api.depends('quality_check_todo')
    def _compute_validate_button_style(self):
        super()._compute_validate_button_style()
        for picking in self:
            if picking.validate_button_style == 'primary' and picking.quality_check_todo:
                picking.validate_button_style = 'secondary'

    def _compute_check(self):
        for picking in self:
            todo = False
            fail = False
            # Only prefetch needed QC fields to avoid to bloat the cache by fetching other QC data.
            checks = picking.check_ids
            checks.fetch(['quality_state'])
            for check in checks:
                if check.quality_state == 'none':
                    todo = True
                elif check.quality_state == 'fail':
                    fail = True
                if fail and todo:
                    break
            picking.quality_check_fail = fail
            picking.quality_check_todo = todo

    def _search_quality_check_todo(self, operator, value):
        if operator != 'in':
            return NotImplemented

        domain = [('picking_id', '!=', False), ('quality_state', '=', 'none')]
        query_check_picking = self.env['quality.check']._search(domain)
        return [('id', 'in', query_check_picking.subselect(query_check_picking.table.picking_id))]

    def _compute_quality_alert_count(self):
        for picking in self:
            picking.quality_alert_count = len(picking.quality_alert_ids)

    def _checks_to_do(self):
        check_ids_to_do = OrderedSet()
        checkable_lines_ids = OrderedSet()
        for picking in self:
            has_picked = True
            if all(not move.picked for move in picking.move_ids):
                checkable_lines = picking.move_line_ids
                has_picked = False
            else:
                checkable_lines = picking.move_line_ids.filtered(
                    lambda ml: ml._is_checkable(check_picked=has_picked)
                )
            checkable_products = checkable_lines.product_id
            checks_to_do = self.check_ids.filtered(
                lambda qc: qc._is_to_do(checkable_products, check_picked=has_picked)
            )
            check_ids_to_do.update(checks_to_do.ids)
            checkable_lines_ids.update(checkable_lines.ids)
        # raise user error for checkable by quantity, picked and tracked products where lot is not set
        all_checks_to_do = self.env['quality.check'].browse(check_ids_to_do)
        all_checkable_lines = self.env['stock.move.line'].browse(checkable_lines_ids)
        check_to_do_on_move_lines = all_checks_to_do.filtered(lambda check: check.measure_on == "move_line")
        tracked_checkable_lines_without_lot = all_checkable_lines.filtered(
            lambda ml: ml.product_id.tracking in ["serial", "lot"] and
            (ml.picking_type_use_create_lots or ml.picking_type_use_existing_lots) and
            not ml.lot_id and not ml.lot_name and
            ml.product_id in check_to_do_on_move_lines.product_id
            )
        if tracked_checkable_lines_without_lot:
            products_list = "\n".join(f"- {product.display_name}" for product in tracked_checkable_lines_without_lot.product_id)
            raise UserError(
                _(
                    "You need to supply a Lot/Serial Number for product:\n%(products)s",
                    products=products_list,
                ),
            )
        return all_checks_to_do

    def check_quality(self):
        checks = self._checks_to_do()
        if checks:
            return checks.action_open_quality_check_wizard()
        return True

    def _create_backorder(self, backorder_moves=None, from_manual_backorder=False):
        res = super()._create_backorder(backorder_moves, from_manual_backorder)
        if self.env.context.get('skip_check'):
            return res
        for backorder in res:
            # Do not link the QC of move lines with quantity of 0 in backorder.
            backorder.move_line_ids.filtered(lambda ml: not ml.uom_id.is_zero(ml.quantity)).check_ids.picking_id = backorder
            if backorder.backorder_id.state in ('done', 'cancel'):
                done_products = backorder.backorder_id.move_ids.filtered(lambda m: m.state == 'done').product_id
                checks_to_unlink = backorder.backorder_id.check_ids.filtered(
                    lambda qc: qc.quality_state == 'none' and qc.product_id not in done_products
                )
                checks_to_unlink.sudo().unlink()

            backorder.move_ids._create_quality_checks()
            backorder.move_ids._create_quality_checks()
        return res

    def _action_done(self):
        if self._check_for_quality_checks():
            raise UserError(_('You still need to do the quality checks!'))
        return super(StockPicking, self)._action_done()

    def _pre_action_done_hook(self):
        pickings_to_check_quality = self._check_for_quality_checks()
        if pickings_to_check_quality:
            return pickings_to_check_quality.check_quality()
        return super()._pre_action_done_hook()

    def _check_for_quality_checks(self):
        if self.env.user.has_group('quality.group_quality_manager'):
            # Quality manager users can ignore QC to do and validate pickings straight away.
            return self.env['stock.picking']

        quality_pickings = self.env['stock.picking']
        for picking in self:
            if picking._checks_to_do():
                quality_pickings |= picking
        return quality_pickings

    def action_cancel(self):
        res = super(StockPicking, self).action_cancel()
        self.sudo().mapped('check_ids').filtered(lambda x: x.quality_state == 'none').unlink()
        return res

    def action_open_quality_check_picking(self):
        action = self.env["ir.actions.actions"]._for_xml_id("quality_control.quality_check_action_picking")
        action['context'] = self.env.context.copy()
        action['context'].update({
            'search_default_picking_id': [self.id],
            'default_picking_id': self.id,
            'show_lots_text': self.show_lots_text,
        })
        return action

    def action_open_on_demand_quality_check(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("quality_control.quality_check_action_main")
        action['views'] = [(False, 'form')]
        action['context'] = {
            **self.env.context,
            'default_product_id': self.product_id.id if len(self.move_ids.ids) == 1 else False,
            'default_product_tmpl_id': self.move_ids.product_tmpl_id.ids,
            'default_picking_id': self.id,
        }
        return action

    def button_quality_alert(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("quality_control.quality_alert_action_check")
        action['views'] = [(False, 'form')]
        action['context'] = {
            'default_product_id': self.product_id.id,
            'default_picking_id': self.id,
        }
        return action

    def open_quality_alert_picking(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("quality_control.quality_alert_action_check")
        action['context'] = {
            'default_product_id': self.product_id.id,
            'default_picking_id': self.id,
        }
        action['domain'] = [('id', 'in', self.quality_alert_ids.ids)]
        action['views'] = [(False, 'list'), (False, 'form')]
        if self.quality_alert_count == 1:
            action['views'] = [(False, 'form')]
            action['res_id'] = self.quality_alert_ids.id
        return action

    def _add_to_wave_post_picking_split_hook(self):
        """
        As moves might have been transfered from one picking to an other or created and assigned
        by passing the confirmation process,we need to clean the obsolete checks per product and
        to recreate checks per operation and products on the newly created pickings.
        """
        super()._add_to_wave_post_picking_split_hook()
        # clean obsolete checks
        checks_by_picking = self.check_ids.filtered(lambda qc: qc.measure_on in ('operation', 'product') and qc.quality_state == 'none').grouped('picking_id')
        checks_ids_to_unlink = set()
        for picking, checks in checks_by_picking.items():
            products = picking.move_ids.product_id
            for check in checks:
                if check.measure_on == 'operation' or (check.measure_on == 'product' and check.product_id not in products):
                    checks_ids_to_unlink.add(check.id)
        self.env['quality.check'].browse(checks_ids_to_unlink).sudo().unlink()
        # recreated product and operation checks
        self.move_ids.sudo()._create_quality_checks()
