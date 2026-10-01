import { GanttArchParser } from "@web_gantt/gantt_arch_parser";


export class MRPWorkorderGanttArchParser extends GanttArchParser {

    parse(arch) {
        const archInfo = super.parse(arch);
        archInfo.defaultRescheduleMethod = "consumeBuffer";
        return archInfo;
    }
}
