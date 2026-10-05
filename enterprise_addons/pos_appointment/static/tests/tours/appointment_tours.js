import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as PosAppointment from "@pos_appointment/../tests/tours/utils/appointment_tours_util";
import { registry } from "@web/core/registry";
const { DateTime } = luxon;

registry.category("web_tour.tours").add("test_appointment_kanban_view_date_filter", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            {
                trigger: ".pos-leftheader button:contains('Booking')",
                run: "click",
            },
            {
                content: "Go to kanban view",
                trigger: "button.o_switch_view.o_kanban",
                run: "click",
            },
            {
                content: "Check that the date filter is applied by default",
                trigger: `.pos .date-filter:contains('${DateTime.now().toFormat("ccc, MMM d")}')`,
            },
            {
                content: "Remove the date filter",
                trigger: ".pos .date-filter i[data-icon='close']",
                run: "click",
            },
            {
                content: "Check that the date filter is not applied anymore",
                trigger: ".pos .date-filter:contains(Select Date)",
            },
        ].flat(),
});

registry.category("web_tour.tours").add("test_appointment_gantt_filters_reset", {
    steps: () => {
        const eveningTime = DateTime.now().set({ hour: 16, minute: 0 }).toMillis();
        return [
            Chrome.withTimeFreeze(eveningTime, [
                Chrome.startPoS(),
                Dialog.confirm("Open Register"),
                {
                    trigger: ".pos-leftheader button:contains('Booking')",
                    run: "click",
                },
                PosAppointment.isGanttViewShown(),
                PosAppointment.checkGanttPillInfo("Morning Booking", "6:00"),
                PosAppointment.switchToView("kanban"),
                PosAppointment.switchToView("gantt"),
                PosAppointment.checkGanttPillInfo("Morning Booking", "6:00"),
            ]),
        ].flat();
    },
});
