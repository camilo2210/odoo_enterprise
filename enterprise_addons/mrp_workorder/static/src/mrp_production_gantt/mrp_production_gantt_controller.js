import { GanttController } from "@web_gantt/gantt_controller";

export class MRPProductionGanttController extends GanttController {
    getAdditionalContext() {
        return this.model.getDialogContext({ withDefault: true });
    }
}
