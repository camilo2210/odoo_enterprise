# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class PosPrepLine(models.Model):
    _inherit = 'pos.prep.line'

    @api.ondelete(at_uninstall=False)
    def _notify_pdis_on_unlink(self):
        for pdis in self.stage_id.prep_display_ids:
            pdis._send_load_orders_message()

    @api.model
    def apply_stage_from_source(self, line_pairs):
        all_uuids = [uuid for pair in line_pairs for uuid in pair]
        lines_by_uuid = {l.uuid: l for l in self.search([('uuid', 'in', all_uuids)])}
        pdis_to_notify = set()
        lines_to_unlink = self.env['pos.prep.line']
        for source_uuid, new_uuid in line_pairs:
            source = lines_by_uuid.get(source_uuid)
            new_line = lines_by_uuid.get(new_uuid)
            if source and new_line and source.stage_id:
                new_line.write({
                    'stage_id': source.stage_id.id,
                    'last_stage_id': source.last_stage_id.id,
                    'todo': source.todo,
                    'last_stage_change': source.last_stage_change,
                    'prep_display_ids': source.prep_display_ids,
                })
                pdis_to_notify.update(new_line.stage_id.prep_display_ids.ids)
                if source.quantity == 0:
                    lines_to_unlink |= source
        lines_to_unlink.unlink()
        for pdis in self.env['pos.prep.display'].browse(list(pdis_to_notify)):
            pdis._send_load_orders_message()
