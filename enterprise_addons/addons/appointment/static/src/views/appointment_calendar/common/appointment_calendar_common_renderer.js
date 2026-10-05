import { useAppointmentRendererHook } from "@appointment/views/appointment_calendar/hooks";
import { AttendeeCalendarCommonRenderer } from "@calendar/views/attendee_calendar/common/attendee_calendar_common_renderer";
import { patch } from "@web/core/utils/patch";
import { renderToFragment } from "@web/core/utils/render";

export class AppointmentAttendeeCalendarCommonRenderer extends AttendeeCalendarCommonRenderer {
    /**
     * @override
     * We show available slots as background events to display the availability of the appointment.
     * Specifically it is done by using the "inverse-background" display, which paints the region
     * except the appointment slots
     */
    mapRecordsToEvents() {
        const { active_model, active_id } = this.props.model.meta.context;
        return [
            ...(active_model === "appointment.type" && active_id
                ? this.convertAvailableSlotsToEvents(this.props.model.data.availableSlots)
                : []),
            ...super.mapRecordsToEvents(...arguments),
        ];
    }

    /**
     * @override
     */
    onEventClick(info) {
        // Prevent opening popover on clicking unavailable slot events
        if (!info.event.extendedProps?.isUnavailableSlot) {
            return super.onEventClick(...arguments);
        }
    }

    convertAvailableSlotsToEvents(slots) {
        if (!slots.length) {
            return [
                {
                    // To make sure the whole calendar is painted as unavailable when there is no slot
                    classNames: ["o_appointment_unavailable_slot"],
                    display: "background",
                    end: this.props.model.data.range.end.toFormat("yyyy-MM-dd HH:mm:ss"),
                    id: "slot_0",
                    isUnavailableSlot: true,
                    start: this.props.model.data.range.start.toFormat("yyyy-MM-dd HH:mm:ss"),
                },
            ];
        }
        return slots.map((slot, idx) => ({
            allDay: slot.allday,
            classNames: ["o_appointment_unavailable_slot"],
            // inverse-background paints the region unoccupied by the events with same groupId
            display: "inverse-background",
            end: slot.end,
            groupId: "available-slot",
            id: `slot_${idx}`,
            isUnavailableSlot: true,
            start: slot.start,
        }));
    }
}

patch(AttendeeCalendarCommonRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        const fns = useAppointmentRendererHook([this.fc]);
        Object.assign(this, fns);
    },

    get interactiveOptions() {
        return {
            ...super.interactiveOptions,
            eventMouseEnter: this.onEventMouseEnter,
            eventMouseLeave: this.onEventMouseLeave,
        };
    },

    get options() {
        const options = super.options;
        if (this.getEventTimeFormat) {
            options.eventTimeFormat = this.getEventTimeFormat();
        }
        options.eventAllow = this.onEventAllow.bind(this);
        return options;
    },

    /**
     * @override
     */
    mapRecordsToEvents() {
        return [
            ...super.mapRecordsToEvents(...arguments),
            ...Object.values(this.props.model.data.slots).flatMap((slot) =>
                this.convertSlotToEvents(slot)
            ),
        ];
    },

    /**
     * Generate fc events based on slots. For recurring slots we generate events
     * for the whole range manually to avoid issues due to different timezones between
     * the user and the appointment type.
     *
     * As such this returns a list of events for each slot.
     */
    convertSlotToEvents(record) {
        const appointmentData = this.props.model.slotsAppointmentData() ?? {};
        const base = {
            title: record.title,
            slotId: record.slotId,
            editable: appointmentData.user_can_manage_slots,
        };
        if (record.slot_type !== "recurring") {
            const event = this.convertRecordToEvent(record);
            // undo the "fake" allday conversion that's normally applied to long events
            if (event.allDay && !record.isAllDay) {
                event.allDay = false;
                event.end = record.end.toISO();
            }
            return [{ ...event, ...base }];
        }
        // For recurring slots, create events for each displayed day. We cannot use fullcalendars implementation of recurring events
        // because the recurrence depends on the timezone of the appointment type rather than the current user.
        // The offset between two timezones can change over the course of the year (daylight saving) so just offsetting the hours does not work.
        const { startDatetime, endDatetime } = appointmentData;
        const events = [];
        const tz = appointmentData.appointment_tz;
        const rangeStart = luxon.DateTime.max(
            this.props.model.rangeStart.setZone(tz).startOf("day").minus({ days: 1 }), // start 1 day early for tz shift
            startDatetime || luxon.DateTime.fromObject({ year: -10000 })
        );
        // look for the first valid datetime that can be an instance of the recurrence
        let currentStart = rangeStart
            .startOf("week") // this is always the previous monday, regardless of locale
            .plus({ days: parseInt(record.weekday) - 1 }) // weekday: 1 = monday
            .set({
                hour: Math.floor(record.start_hour),
                minute: Math.round((record.start_hour % 1) * 60),
            });
        if (currentStart < rangeStart) {
            currentStart = currentStart.plus({ weeks: 1 });
        }
        let currentEnd = currentStart.set({
            hour: Math.floor(record.end_hour),
            minute: Math.round((record.end_hour % 1) * 60),
        });
        const rangeEnd = luxon.DateTime.min(
            this.props.model.rangeEnd.setZone(tz).startOf("day").plus({ days: 1 }),
            endDatetime || luxon.DateTime.fromObject({ year: 10000 })
        );
        while (currentStart <= rangeEnd) {
            events.push({
                ...base,
                slotType: "recurring",
                start: currentStart.toISO(),
                end: currentEnd.toISO(),
            });
            currentStart = currentStart.plus({ weeks: 1 });
            currentEnd = luxon.DateTime.min(currentEnd.plus({ weeks: 1 }), rangeEnd);
        }
        return events;
    },

    /**
     * @override
     */
    fcEventToRecord(event, forceAllDay = false) {
        if (!event.extendedProps || !event.extendedProps.slotId) {
            return super.fcEventToRecord(...arguments);
        }
        const storedSlot = this.props.model.data.slots[event.extendedProps.slotId];
        return {
            ...super.fcEventToRecord(...arguments),
            slotId: event.extendedProps.slotId,
            slotType: event.extendedProps.slotType,
            // FullCalendar renders any event spanning >= 24h as all-day; trust the slot's
            // stored all-day value instead (as the base renderer does for regular records
            // via existingRecord) so a timed slot isn't persisted as all-day when moved or
            // resized. Recurring slots have no stored value, hence the fallback.
            isAllDay: forceAllDay ? event.allDay : storedSlot?.isAllDay ?? event.allDay,
        };
    },

    /**
     * @overrde
     */
    onEventClick(info) {
        const { event, jsEvent } = info;
        if (event.extendedProps.slotId) {
            // startEditable <=> editable in this app
            if (event.startEditable) {
                jsEvent.preventDefault();
                jsEvent.stopPropagation();
                event.remove();
                this.props.model.removeSlot(event.extendedProps.slotId);
            }
            return;
        }
        return super.onEventClick(...arguments);
    },

    /**
     * @override
     */
    eventClassNames({ event }) {
        const classesToAdd = super.eventClassNames(...arguments);
        if (event.extendedProps.slotId) {
            classesToAdd.push("o_calendar_slot");
        } else if (this.props.model.selectedAppointmentTypeId()) {
            const calendarEvent = this.props.model.records[event.id];
            if (
                calendarEvent &&
                (!calendarEvent.rawRecord.appointment_type_id ||
                    calendarEvent.rawRecord.appointment_type_id[0] !==
                        this.props.model.selectedAppointmentTypeId())
            ) {
                classesToAdd.push("opacity-50");
            }
        }
        return classesToAdd;
    },

    /**
     * @override
     */
    onEventContent(arg) {
        const { event } = arg;
        if (event.extendedProps.slotId) {
            const slotStart = luxon.DateTime.fromJSDate(event.start);
            let slotEnd = luxon.DateTime.fromJSDate(event.end);
            const subslots = [];
            let hasOverlap = false;
            const appointmentData = this.props.model.slotsAppointmentData();
            // may happen for slots that were previously allday
            if (!slotEnd?.isValid) {
                const slotDurationHours =
                    appointmentData?.category_slot_scheduling === "flexible"
                        ? this.props.model.getLocalStorageDuration(appointmentData?.id)
                        : appointmentData.appointment_duration;
                slotEnd = slotStart.plus({ hours: slotDurationHours || 0.5 });
            }
            // Recurring slots are subdivided into the bookable subslots the front-end would
            // generate: one every `slot_creation_interval` hours, each `appointment_duration`
            // hours long. They are displayed proportionally inside the larger slot, unless they
            // cannot fit in which case they will appear as a scrollable list.
            if (event.extendedProps.slotType === "recurring") {
                // 1 slot may be split into multiple fc displayed events (here called "segments")
                // if it wraps around to the following day (1 segment per day)
                // each one should only contain subslots starting or ending on that day

                // As we know recurring slots cannot be more than 24 hours long, there can only be two segments
                // so we can use isStart and isEnd to know what half we are in. Otherwise we would need to
                // edit them once they are mounted.
                let segmentStart = slotStart;
                let segmentEnd = slotEnd;
                if (arg.isStart && !arg.isEnd) {
                    segmentEnd = slotStart.endOf("day");
                } else if (arg.isEnd && !arg.isStart) {
                    segmentStart = slotEnd.startOf("day");
                }

                const subslotDurationMinutes = (appointmentData?.appointment_duration || 0) * 60;
                const createIntervalMinutes = (appointmentData?.slot_creation_interval || 0) * 60;
                // slots are also considered to "overlap" if they would otherwise be unreadable due to small height
                hasOverlap =
                    createIntervalMinutes < subslotDurationMinutes || subslotDurationMinutes < 15;

                // we have two types of "subslots" for rendering: an actual subslot and a gap
                // as it's possible for the second segment to start with a gap, they need to be actual items in the list

                // walk every subslot from the slot start and keep the ones in this segment. For the
                // proportional layout, "in segment" means overlapping it, so a subslot straddling a
                // boundary is clamped and shown as a partial on both sides; for the overlap list a
                // subslot belongs to the segment it starts in (avoids showing it in both).
                // recurring appointments always define a duration and creation interval, but a
                // zero interval would spin the loop below forever: guard against inconsistent data
                if (subslotDurationMinutes > 0 && createIntervalMinutes > 0) {
                    let subslotStart = slotStart;
                    // set last shown end to segment start to create a starting gap if necessary
                    let shownEnd = segmentStart;

                    while (subslotStart < segmentEnd) {
                        const subslotEnd = subslotStart.plus({ minutes: subslotDurationMinutes });
                        // keep the subslots overlapping this segment, but never one running past the
                        // slot's end (it would not be bookable) - note segmentEnd is the day boundary
                        // for a slot spilling into the next day, so we clamp on slotEnd, not segmentEnd
                        if (subslotEnd > segmentStart && subslotEnd <= slotEnd) {
                            // shown start/end correspond are clamped down to the start and end of the segment
                            const shownStart = luxon.DateTime.max(subslotStart, segmentStart);
                            // create gap based on previous end, before updating the end
                            if (!hasOverlap) {
                                const gapMinutes = shownStart.diff(shownEnd, "minutes").minutes;
                                if (gapMinutes > 0) {
                                    subslots.push({ isGap: true, flexWeight: gapMinutes });
                                }
                            }
                            shownEnd = luxon.DateTime.min(subslotEnd, segmentEnd);
                            subslots.push({
                                flexWeight: shownEnd.diff(shownStart, "minutes").minutes,
                                startFormatted: subslotStart.toFormat(this.timeFormat),
                                endFormatted: subslotEnd.toFormat(this.timeFormat),
                            });
                        }
                        subslotStart = subslotStart.plus({ minutes: createIntervalMinutes });
                    }
                    if (!hasOverlap) {
                        const gapMinutes = segmentEnd.diff(shownEnd, "minutes").minutes;
                        if (gapMinutes > 0) {
                            subslots.push({ isGap: true, flexWeight: gapMinutes });
                        }
                    }
                    const bookableSlots = subslots.filter((subslot) => !subslot.isGap);
                    if (bookableSlots.length) {
                        bookableSlots.at(0).isFirst = true;
                        bookableSlots.at(-1).isLast = true;
                    }
                }
            }
            const fragment = renderToFragment("appointment.AttendeeCalendarCommonRenderer.slot", {
                event,
                eventDurationMinutes: slotEnd.diff(slotStart, "minutes").minutes,
                slotStartFormatted: slotStart.toFormat(this.timeFormat),
                slotEndFormatted: slotEnd.toFormat(this.timeFormat),
                subslots,
                hasOverlap,
            });
            return { domNodes: fragment.children };
        }
        return super.onEventContent(arg);
    },

    /**
     * @override
     */
    isSelectionAllowed(event) {
        const result = super.isSelectionAllowed(...arguments);
        if (this.isSlotCreationMode()) {
            return this.isSlotSelectionAllowedFromValues(event);
        }
        return result;
    },

    /**
     * @param {object} eventValues {start, end}
     * @returns whether this slot is allowed to exist
     */
    isSlotSelectionAllowedFromValues(eventValues) {
        const appointmentData = this.props.model.slotsAppointmentData();
        if (!appointmentData?.user_can_manage_slots) {
            return false;
        }
        // allday only makes sense for custom appointments
        if (appointmentData.category !== "custom" && eventValues.allDay) {
            return false;
        }
        // reject slots falling outside the appointment's [start, end] booking window (punctual types)
        if (
            appointmentData.startDatetime
            && luxon.DateTime.fromJSDate(eventValues.start).toISODate() < appointmentData.startDatetime.toISODate()
        ) {
            return false;
        }
        if (
            appointmentData.endDatetime
            && luxon.DateTime.fromJSDate(eventValues.end).toISODate() > appointmentData.endDatetime.toISODate()
        ) {
            return false;
        }
        // limit the drag length to 24 hours to prevent users from accidentally creating a billion slots
        const start = luxon.DateTime.fromJSDate(eventValues.start);
        const end = luxon.DateTime.fromJSDate(eventValues.end);
        if (end > start.plus({ days: 1 }).endOf("day")) {
            return false;
        }
        // weekly slots are weekday/hour patterns, they can be placed on any date
        if (appointmentData.category_slot_scheduling === "weekly") {
            return true;
        }
        // otherwise the slot must not start in the past; for punctual types the
        // [start, end] window was already enforced above
        return start > luxon.DateTime.now();
    },

    /**
     * @override
     */
    async onSelect(info) {
        info.jsEvent.preventDefault();
        if (!this.isSlotCreationMode()) {
            return super.onSelect(...arguments);
        }
        const slotRecords = this._getSplitSlotRecords(
            this.fcEventToRecord(info),
            luxon.DateTime.fromJSDate(info.start),
            luxon.DateTime.fromJSDate(info.end)
        );
        await this.props.model.createSlots(slotRecords);
        this.fc().unselect();
    },

    /**
     * Generate a list of slot values of the right duration
     * starting at rangeStart and with at most 1 slot ending after the rangeEnd.
     * At least 1 slot will always be created.
     *
     * If there is no duration of a recurrent appointment is being edited then
     * a single slot of the right length will be created.
     */
    _getSplitSlotRecords(baseRecord, rangeStart, rangeEnd) {
        if (!rangeStart || baseRecord.isAllDay) {
            return [baseRecord];
        }
        const appointmentData = this.props.model.slotsAppointmentData();
        const slotDurationHours =
            appointmentData?.category_slot_scheduling === "flexible"
                ? this.props.model.getLocalStorageDuration(appointmentData?.id)
                : appointmentData.appointment_duration;
        if (!rangeEnd?.isValid) {
            rangeEnd = rangeStart.plus({ hours: slotDurationHours || 0.5 });
        }
        // set appointment tz for recurring appointments to ensure we split at midnight
        // with respect to that timezone, not the locale one
        if (
            appointmentData?.category_slot_scheduling === "weekly" &&
            appointmentData?.appointment_tz
        ) {
            rangeStart = rangeStart.setZone(appointmentData.appointment_tz);
            rangeEnd = rangeEnd.setZone(appointmentData.appointment_tz);
        }
        const slotRecords = [];
        let slotStart = rangeStart;
        if (appointmentData?.category_slot_scheduling === "flexible" && slotDurationHours) {
            while (slotStart < rangeEnd) {
                const slotEnd = slotStart.plus({
                    hours: slotDurationHours,
                });
                slotRecords.push({ ...baseRecord, start: slotStart, end: slotEnd });
                slotStart = slotEnd;
            }
        } else if (
            appointmentData?.category_slot_scheduling === "weekly" &&
            slotStart.endOf("day") <= rangeEnd
        ) {
            while (slotStart.endOf("day") <= rangeEnd) {
                slotRecords.push({ ...baseRecord, start: slotStart, end: slotStart.endOf("day") });
                slotStart = slotStart.plus({ days: 1 }).startOf("day");
            }
            const lastDurationMinutes = rangeEnd.diff(slotStart, "minutes").minutes;
            if (lastDurationMinutes >= 0) {
                slotRecords.push({
                    ...baseRecord,
                    start: slotStart,
                    end: slotStart.plus({
                        minutes: Math.max(lastDurationMinutes, slotDurationHours * 60),
                    }),
                });
            }
        } else {
            slotRecords.push({ ...baseRecord, start: rangeStart, end: rangeEnd });
        }
        return slotRecords;
    },

    /**
     * @override
     */
    async onDateClick(info) {
        if (info.jsEvent.defaultPrevented) {
            return;
        }
        if (!this.isSlotCreationMode()) {
            return super.onDateClick(...arguments);
        }
        // true allday events are not valid on repeating appointments
        if (this.props.model.slotsAppointmentData().category_slot_scheduling === "weekly") {
            return;
        }
        // Disabled in month view
        if (this.props.model.scale === "month") {
            return;
        }
        const date = luxon.DateTime.fromISO(info.dateStr);
        if (date < luxon.DateTime.now()) {
            return;
        }
        await this.props.model.createSlot(this.fcEventToRecord(info));
    },

    /**
     * @override
     */
    async onEventDrop(info) {
        if (!this.isSlotCreationMode()) {
            return super.onEventDrop(...arguments);
        }
        const baseRecord = this.fcEventToRecord(
            info.event,
            info.oldEvent.allDay !== info.event.allDay
        );
        // necessary for recurring case, where we cannot accept multi-day slots
        const [updatedSlot, ...extraSlots] = this._getSplitSlotRecords(
            baseRecord,
            baseRecord.start,
            baseRecord.end
        );
        await this.props.model.updateSlot(updatedSlot, extraSlots);
    },

    /**
     * @override
     */
    async onEventResize(info) {
        if (!this.isSlotCreationMode()) {
            return super.onEventResize(...arguments);
        }
        // extending a slot re-splits the new span the same way creation does
        // (e.g. a flexible slot dragged to 3x its duration becomes 3 subslots)
        const baseRecord = this.fcEventToRecord(info.event);
        const [updatedSlot, ...extraSlots] = this._getSplitSlotRecords(
            baseRecord,
            baseRecord.start,
            baseRecord.end
        );
        await this.props.model.updateSlot(updatedSlot, extraSlots);
    },

    /**
     * @override
     */
    onEventResizeStart(info) {
        if (!this.isSlotCreationMode()) {
            return super.onEventResizeStart(...arguments);
        }
    },

    /*
     * unhide the trash icon on hover
     */
    onEventMouseEnter(info) {
        if (info.event.extendedProps?.slotId && info.event.startEditable) {
            info.el.querySelector(".o_calendar_slot_trash_icon")?.classList?.remove("o_hidden");
        }
    },

    /**
     * rehide the trash icon on leaving hover
     * @override
     */
    onEventMouseLeave(info) {
        if (info.event.extendedProps?.slotId) {
            info.el.querySelector(".o_calendar_slot_trash_icon")?.classList?.add("o_hidden");
        }
    },

    /**
     * Prevent drag & drop events in the past in slot creationmode
     */
    onEventAllow(dropInfo, draggedEvent) {
        if (!this.isSlotCreationMode()) {
            return super.onEventAllow?.(...arguments) || true;
        }
        if (!draggedEvent.extendedProps.slotId) {
            return false;
        }
        return this.isSlotSelectionAllowedFromValues(dropInfo);
    },

});
