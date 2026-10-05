export function isKanbanViewShown() {
    return {
        content: "Check that the booking kanban view is shown",
        trigger: ".pos-content .o_action_manager .o_kanban_view",
    };
}

export function isGanttViewShown() {
    return {
        content: "Check that the booking gantt view is shown",
        trigger: ".pos-content .o_action_manager .o_gantt_view",
    };
}

export function switchToView(view) {
    const checker = view === "kanban" ? isKanbanViewShown : isGanttViewShown;
    return [
        {
            content: `Go to ${view} view`,
            trigger: `button.o_switch_view.o_${view}`,
            run: "click",
        },
        checker(),
    ];
}

/**
 * @param {string} eventName - Expected event name (e.g. "Morning Booking")
 * @param {string} startTime - Expected start time substring in popover (e.g. "6:00")
 */
export function checkGanttPillInfo(eventName, startTime) {
    return [
        {
            content: `Check that the gantt pill shows '${eventName}'`,
            trigger: `.o_gantt_view .o_gantt_pill_title:contains('${eventName}')`,
            run: "click",
        },
        {
            content: `Check that the popover shows the event name '${eventName}'`,
            trigger: `.o_appointment_calendar_event_popover .popover-header:contains('${eventName}')`,
        },
        {
            content: `Check that the popover shows the start time '${startTime}'`,
            trigger: `.o_appointment_calendar_event_popover .popover-body:contains('${startTime}')`,
        },
        {
            content: "Close the popover",
            trigger: ".o_appointment_calendar_event_popover [data-icon='close']",
            run: "click",
        },
    ];
}
