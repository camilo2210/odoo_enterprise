import { GanttArchParser } from "@web_gantt/gantt_arch_parser";

export class PlanningGanttArchParser extends GanttArchParser {
    parse() {
        const archInfo = super.parse(...arguments);
        archInfo.progressBarFields = [...(archInfo.progressBarFields || []) , "role_id", "department_id"];
        return archInfo;
    }
}
