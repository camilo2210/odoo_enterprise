import { models } from "@web/../tests/web_test_helpers";

const { DateTime } = luxon;
export class PosPrepLine extends models.ServerModel {
    _name = "pos.prep.line";

    _load_pos_preparation_data_fields() {
        return [];
    }
    change_state_status(self, todos) {
        for (const prepLineId of self) {
            this.write([prepLineId], {
                todo: todos[String(prepLineId)],
            });
        }
    }

    change_prep_line_stage(self, prep_display_id, kwargs) {
        const direction = kwargs?.direction ?? 1;
        const pdis = this.env["pos.prep.display"].browse([prep_display_id])[0];
        const stages = pdis.stage_ids
            .map((id) => this.env["pos.prep.stage"].browse([id])[0])
            .sort((a, b) => a.sequence - b.sequence || a.id - b.id);

        for (const prepLineId of self) {
            const prepLine = this.env["pos.prep.line"].browse([prepLineId])[0];
            const currentIndex = stages.findIndex((s) => s.id === prepLine.stage_id);
            const newIndex = direction === 0 ? 0 : currentIndex + direction;
            if (newIndex !== currentIndex && newIndex >= 0 && newIndex < stages.length) {
                this.write([prepLineId], {
                    todo: true,
                    stage_id: stages[newIndex].id,
                    last_stage_change: DateTime.now().toFormat("yyyy-MM-dd HH:mm:ss"),
                });
            }
        }
    }
}
