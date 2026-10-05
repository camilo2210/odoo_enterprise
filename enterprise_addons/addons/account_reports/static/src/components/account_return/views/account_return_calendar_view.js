import { calendarView } from "@web/views/calendar/calendar_view";
import { AccountReturnCalendarController } from "./account_return_calendar_controller";
import { registry } from "@web/core/registry";

const AccountReturnCalendarView = {
    ...calendarView,
    Controller: AccountReturnCalendarController,
};

registry.category("views").add("account_return_calendar", AccountReturnCalendarView);
