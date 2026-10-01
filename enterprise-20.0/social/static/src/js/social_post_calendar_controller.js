import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { CalendarController } from "@web/views/calendar/calendar_controller";

export class SocialPostCalendarController extends CalendarController {
    setup() {
        super.setup();
        this.notification = useService("notification");
    }

    createRecord(record) {
        let { start } = record;
        if (record.isAllDay) {
            [start] = this.model.getAllDayDates(start);
        }
        if (start < luxon.DateTime.now()) {
            return this.notification.add(_t("You cannot schedule a post in the past."), {
                type: "warning",
            });
        }
        return super.createRecord(record);
    }
}
