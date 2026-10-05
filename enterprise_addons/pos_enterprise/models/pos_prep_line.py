from odoo import models, fields, api
from odoo.addons.pos_enterprise.utils.date_utils import compute_seconds_since


class PosPrepLine(models.Model):
    _inherit = 'pos.prep.line'

    todo = fields.Boolean("Status of the orderline", help="The status of a command line, todo or not")
    stage_id = fields.Many2one('pos.prep.stage', ondelete='cascade', index=True)
    last_stage_id = fields.Many2one('pos.prep.stage', ondelete='cascade', index=True)
    last_stage_change = fields.Datetime()
    associated_barcodes = fields.Json()

    prep_display_ids = fields.Many2many('pos.prep.display', string="Preparation Displays", compute='_compute_prep_display_ids')
    is_first_stage = fields.Boolean("Is First Stage", compute="_compute_stage_position")
    is_last_stage = fields.Boolean("Is Last Stage", compute="_compute_stage_position")
    is_second_to_last_stage = fields.Boolean("Is Second to Last Stage", compute="_compute_stage_position")

    @api.model
    def _load_pos_data_fields(self, config):
        return [
            'prep_order_id', 'pos_order_line_id', 'quantity', 'uuid', 'cancelled',
            'combo_line_ids', 'product_id', 'attribute_value_ids', 'combo_parent_id',
            'write_date',
        ]

    @api.depends('prep_order_id.pos_order_id.config_id', 'pos_order_line_id.order_id.config_id', 'product_id.pos_categ_ids')
    def _compute_prep_display_ids(self):
        for record in self:
            order = record.prep_order_id.pos_order_id or record.pos_order_line_id.order_id
            if not order:
                record.prep_display_ids = self.env['pos.prep.display']
                continue
            record.prep_display_ids = self.env['pos.prep.display']._get_preparation_displays(
                order,
                record.product_id.pos_categ_ids.ids
            )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._set_preparation_stage()
        return records

    @api.depends('stage_id')
    def _compute_stage_position(self):
        for record in self:
            if not record.stage_id:
                record.is_first_stage = record.is_last_stage = record.is_second_to_last_stage = False
                continue
            stages = record.prep_display_ids.stage_ids.sorted(key=lambda s: (s.sequence, s.id))
            record.is_second_to_last_stage = record.stage_id.id == stages[-2:-1].id
            record.is_last_stage = record.stage_id.id == stages[-1:].id
            record.is_first_stage = record.stage_id.id == stages[:1].id

    def _set_preparation_stage(self):
        for record in self:
            is_combo = record.product_id.type == 'combo'
            is_orphan = not (record.prep_order_id or record.pos_order_line_id)
            # If the line already has a stage, do not set the default one
            # can happen when splitting orders.
            if record.stage_id or is_combo or is_orphan:
                continue
            stages = record.prep_display_ids.stage_ids.sorted(key=lambda s: (s.sequence, s.id))
            record.write({
                'stage_id': stages[:1].id,
                'last_stage_id': stages[-1:].id,
                'todo': True,
                'last_stage_change': fields.Datetime.now(),
            })

    def change_state_status(self, todos):
        prep_line_todos = []

        for prep_line in self:
            prep_line.todo = todos[str(prep_line.id)]
            prep_line_todos.append({
                'id': prep_line.id,
                'todo': prep_line.todo
            })
            prep_line._record_status_change_prep_time()

        for pdis in self.stage_id.prep_display_ids:
            pdis._notify('CHANGE_STATE_STATUS', prep_line_todos)

        return True

    def _record_status_change_prep_time(self):
        self.ensure_one()
        line = self.pos_order_line_id
        for is_stage, field in [
            (self.is_first_stage, 'preparation_time'),
            (self.is_second_to_last_stage, 'service_time'),
        ]:
            if not is_stage:
                continue
            if not self.todo and line[field] == -1:
                line[field] = compute_seconds_since(self.last_stage_change)
            elif self.todo and line[field] != -1:
                line[field] = -1

    def change_prep_line_stage(self, prep_display_id, direction=1):
        pdis_to_notify = {prep_display_id}

        for prep_line in self:
            stages = prep_line.prep_display_ids.stage_ids.sorted(key=lambda s: (s.sequence, s.id))
            current_index = stages.ids.index(prep_line.stage_id.id)
            new_index = 0 if direction == 0 else current_index + direction
            if new_index != current_index and 0 <= new_index < len(stages):
                old_last_stage_change = prep_line.last_stage_change
                prep_line.write({
                    'todo': True,
                    'stage_id': stages[new_index].id,
                    'last_stage_change': fields.Datetime.now(),
                })
                prep_line._record_stage_change_prep_time(old_last_stage_change)
                pdis_to_notify.update(prep_line.stage_id.prep_display_ids.ids)

        for pdis_id in pdis_to_notify:
            pdis = self.env['pos.prep.display'].browse(int(pdis_id))
            pdis._send_load_orders_message()

        return True

    def _record_stage_change_prep_time(self, old_last_stage_change):
        self.ensure_one()
        line = self.pos_order_line_id
        # If new stage is the first one, it means the order has been reset
        if self.is_first_stage:
            if line.preparation_time != -1:
                line.preparation_time = -1
            if line.service_time != -1:
                line.service_time = -1
        # If new stage is the second last one, write the preparation_time
        if self.is_second_to_last_stage and line.preparation_time == -1:
            line.preparation_time = compute_seconds_since(old_last_stage_change)
        # If new stage is the last one, write the service_time and completion_time
        if self.is_last_stage:
            if line.service_time == -1:
                line.service_time = compute_seconds_since(old_last_stage_change)
            # If all quantities are cancelled (no pos_order_line_id), skip completion_time
            order_lines = self.prep_order_id.prep_line_ids.pos_order_line_id
            if order_lines:
                self.prep_order_id.completion_time = int(
                    max(order_lines.mapped(lambda l: l.service_time + l.preparation_time)) / 60
                )

    def update_associated_barcodes(self, associated_barcodes, prep_display_id):
        self.ensure_one()
        self.associated_barcodes = associated_barcodes
        p_dis = self.env['pos.prep.display'].browse(int(prep_display_id))
        p_dis._notify("STATE_BARCODE_UPDATE", {self.id: self.associated_barcodes})
