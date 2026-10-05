import { useService } from "@web/core/utils/hooks";
import { GanttController } from "@web_gantt/gantt_controller";

export class MRPWorkorderGanttController extends GanttController {

    async setup() {
        super.setup();
        this.action = useService("action");
        this.orm = useService("orm");
    }

    get draftProductionIds() {
        return [
            ...new Set(
                this.model.data.records
                    .filter((record) => record.production_state === "draft")
                    .map((record) => record.production_id.id)
            ),
        ];
    }

    async confirmPlanning() {
        await this.orm.call("mrp.production", "action_confirm", [this.draftProductionIds]);
        await this.model.fetchData();
    }

    async selectOrdersToPlan() {
        const action = await this.orm.call(this.props.resModel, "action_select_mo_to_plan", [false]);
        this.action.doAction(
            action,
            {
                onClose: async () => { await this.model.fetchData() },
            }
        );
    }
}
