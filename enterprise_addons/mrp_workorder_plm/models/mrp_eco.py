# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, Command


class MrpEco(models.Model):
    _inherit = 'mrp.eco'

    @api.depends(
        'bom_id.operation_ids.quality_point_ids',
        'new_bom_id.operation_ids.quality_point_ids',
        'bom_id.operation_ids.quality_point_ids.test_type_id',
        'new_bom_id.operation_ids.quality_point_ids.test_type_id',
        'bom_id.operation_ids.quality_point_ids.note',
        'new_bom_id.operation_ids.quality_point_ids.note')
    def _compute_routing_change_ids(self):
        return super()._compute_routing_change_ids()

    def _prepare_detailed_change_commands(self, new_op, old_op):
        commands = []
        new_points = new_op.quality_point_ids
        new_point_dict = dict(((p.title, p.note), p) for p in new_points)
        if old_op:
            for old_point in old_op.quality_point_ids:
                new_point = new_point_dict.get((old_point.title, old_point.note), False)
                if new_point:
                    del new_point_dict[(old_point.title, old_point.note)]
                    if old_point.test_type_id == new_point.test_type_id:
                        continue
                    else:
                        commands += [Command.create({
                            'change_type': 'update',
                            'workcenter_id': new_op.workcenter_id.id,
                            'operation_id': new_op.id,
                            'quality_point_id': new_point.id,
                            'old_quality_point_id': old_point.id,
                        })]
                else:
                    commands += [Command.create({
                        'change_type': 'update',
                        'workcenter_id': new_op.workcenter_id.id,
                        'operation_id': old_op.id,
                        'old_quality_point_id': old_point.id,
                    })]
        for new_point in new_point_dict.values():
            commands += [Command.create({
                'change_type': 'update',
                'workcenter_id': new_op.workcenter_id.id,
                'operation_id': new_op.id,
                'quality_point_id': new_point.id,
            })]
        return commands


class MrpEcoRoutingChange(models.Model):
    _inherit = 'mrp.eco.routing.change'

    quality_point_id = fields.Many2one('quality.point', ondelete='cascade')
    old_quality_point_id = fields.Many2one('quality.point')
    title = fields.Char(related='quality_point_id.title', string='Title')
    description_reference = fields.Reference(selection_add=[('quality.point', 'Quality Point')])

    @api.depends('quality_point_id', 'old_quality_point_id')
    def _compute_description_reference(self):
        super()._compute_description_reference()
        for op_change in self:
            point = op_change.quality_point_id or op_change.old_quality_point_id
            if point:
                op_change.description_reference = point

    @api.depends('quality_point_id', 'old_quality_point_id')
    def _compute_description(self):
        super()._compute_description()
        for op_change in self:
            if op_change.change_type != 'update':
                continue
            if not op_change.quality_point_id and not op_change.old_quality_point_id:
                continue
            if op_change.quality_point_id and op_change.old_quality_point_id:
                # Step type updated
                old_type = op_change.old_quality_point_id.test_type_id.display_name or ''
                new_type = op_change.quality_point_id.test_type_id.display_name or ''
                op_change.description = self.env._(
                    "Update: %(title)s\t-\tType: %(old_type)s -> %(new_type)s",
                    title=op_change.quality_point_id.title,
                    old_type=old_type,
                    new_type=new_type,
                )
            elif op_change.quality_point_id:
                # Step added
                point = op_change.quality_point_id
                parts = [self.env._("Add: %(title)s", title=point.title)] if point.title else [self.env._("Add")]
                if point.test_type_id:
                    parts.append(self.env._("\t-\tType: %(type)s", type=point.test_type_id.display_name))
                op_change.description = '\n'.join(parts)
            else:
                # Step deleted
                point = op_change.old_quality_point_id
                parts = [self.env._("Delete: %(title)s", title=point.title)] if point.title else [self.env._("Delete")]
                if point.test_type_id:
                    parts.append(self.env._("\t-\tType: %(type)s", type=point.test_type_id.display_name))
                op_change.description = '\n'.join(parts)
