import { CalendarCommonRenderer } from "@web/views/calendar/calendar_common/calendar_common_renderer";

export class SocialPostCommonRenderer extends CalendarCommonRenderer {
    static eventTemplate = "social.SocialPostCommonRenderer.event";

    get interactiveOptions() {
        return {
            ...super.interactiveOptions,
            selectable: false,
        };
    }

    eventClassNames({ el, event }) {
        const classesToAdd = super.eventClassNames(...arguments);

        const record = this.props.model.records[event.id];
        if (record.rawRecord.state === "draft") {
            classesToAdd.push("bg-300");
        } else if (record.rawRecord.state === "posted") {
            classesToAdd.push("bg-success");
        } else if (["scheduled", "posting"].includes(record.rawRecord.state)) {
            classesToAdd.push("bg-info");
        }

        return classesToAdd.filter((c) => !["o_event_hatched", "o_event_dot"].includes(c));
    }
}
