import { computed, t, useEffect, useProps } from "@odoo/owl";
import { is24HourFormat } from "@web/core/l10n/time";
import { useEnv } from "@web/owl2/utils";

const FORMAT_12_HOUR = {
    hour: "numeric",
    minute: "2-digit",
    omitZeroMinute: true,
    meridiem: "short",
};
const FORMAT_24_HOUR = {
    hour: "numeric",
    minute: "2-digit",
    hour12: false,
};

/**
 * Common code between common and year renderer for our calendar.
 *
 * @param {(() => any)[]} fcInstanceGetters
 */
export function useAppointmentRendererHook(fcInstanceGetters) {
    const env = useEnv();
    const props = useProps({ model: t.object() });

    /**
     * Display an overlay when using the slots selection mode that
     * encompasses the past time.
     */
    useEffect(() => {
        const editingAppointmentData = props.model.slotsAppointmentData();
        if (env.calendarState.mode === "default" || !editingAppointmentData) {
            return;
        }
        const appointmentStart = editingAppointmentData.startDatetime?.toLocal().toISODate();
        const appointmentEnd = editingAppointmentData.endDatetime?.toLocal().toISODate();
        const addedElements = [];
        const shadedDays = [];
        const fcElements = [];
        for (const getFcInstance of fcInstanceGetters) {
            const fc = getFcInstance();
            if (!fc) {
                continue;
            }

            // Main element
            if (env.calendarState.mode === "slots-creation") {
                fc.el.classList.add("o_calendar_slots_in_creation");
            }
            fcElements.push(fc.el);


            // Days to shade
            const daysToShade = [
                ...fc.el.querySelectorAll(".fc-day:not(.fc-col-header-cell)"),
            ].filter((dayColumn) => {
                const colDate = dayColumn.dataset.date;
                return (
                    // before the appointment window starts if it has a start
                    (appointmentStart && colDate < appointmentStart) ||
                    // otherwise start = today so shade everything in the past and today
                    (!appointmentStart && !dayColumn.classList.contains("fc-day-future")) ||
                    // and after the appointment window ends if it has an end
                    (appointmentEnd && colDate > appointmentEnd)
                );
            });
            for (const dayToShade of daysToShade) {
                dayToShade.classList.add("o_calendar_slot_selection");
            }
            shadedDays.push(...daysToShade);

            // Create a block for today to have the overlay size based on the current hour
            const todayColumn = fc.el.querySelectorAll(".fc-day-today:not(.fc-col-header-cell)")[1];
            const bgColumn = todayColumn?.querySelector(".fc-timegrid-col-bg");
            const nowIndicator = todayColumn?.querySelector(".fc-timegrid-now-indicator-line");
            if (
                daysToShade.includes(todayColumn) && // unless it's not supposed to be shaded at all
                !appointmentStart && // unless there is a start, then it's either fully shaded or not
                !(appointmentEnd && appointmentEnd > todayColumn.dataset.date) && // unless it is after the end
                bgColumn &&
                nowIndicator &&
                ["timeGridWeek", "timeGridDay"].includes(fc.view.type)
            ) {
                const childEl = document.createElement("div");
                childEl.classList.add(
                    "o_calendar_slot_selection_now",
                    "position-absolute",
                    "start-0",
                    "end-0"
                );
                const height = nowIndicator.style.top.slice(0, -2);
                if (height) {
                    childEl.style.height = `${height}px`;
                }
                bgColumn.appendChild(childEl);
                addedElements.push(childEl);
            }
        }
        return function cleanup() {
            for (const fcEl of fcElements) {
                fcEl.classList.remove("o_calendar_slots_in_creation");
            }
            for (const shadedDay of shadedDays) {
                shadedDay.classList.remove("o_calendar_slot_selection");
            }
            for (const childEl of addedElements) {
                childEl.remove();
            }
        };
    });

    useEffect(() => {
        // force render on selection change to update opacity
        props.model.selectedAppointmentTypeId();
        for (const fcGetter of fcInstanceGetters) {
            const fc = fcGetter();
            if (fc) {
                fc.render();
            }
        }
    });

    return {
        isSlotCreationMode: computed(() => env.calendarState.mode === "slots-creation"),
        getEventTimeFormat: () => (is24HourFormat() ? FORMAT_24_HOUR : FORMAT_12_HOUR),
    };
}
