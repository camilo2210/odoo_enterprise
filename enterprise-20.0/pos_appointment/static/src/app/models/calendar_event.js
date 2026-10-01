import { registry } from "@web/core/registry";
import { Base } from "@point_of_sale/app/models/related_models";

export class CalendarEvent extends Base {
    static pythonModel = "calendar.event";

    get attendeeName() {
        return this.partner_ids?.[0]?.name || this.name;
    }
}

registry.category("pos_available_models").add(CalendarEvent.pythonModel, CalendarEvent);
