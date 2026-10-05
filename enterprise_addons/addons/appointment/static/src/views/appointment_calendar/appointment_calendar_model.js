import { proxy, signal } from "@odoo/owl";

import { AttendeeCalendarModel } from "@calendar/views/attendee_calendar/attendee_calendar_model";
import { deserializeDateTime, serializeDateTime } from "@web/core/l10n/dates";
import { unique } from "@web/core/utils/arrays";
import { Cache } from "@web/core/utils/cache";
import { patch } from "@web/core/utils/patch";
import { user } from "@web/core/user";
import { rpc } from "@web/core/network/rpc";


export const APT_SIDEPANEL_LIST_PAST_FLEXIBLE_DISPLAY_LIMIT = { weeks: 2 };

export class AppointmentAttendeeCalendarModel extends AttendeeCalendarModel {
    setup() {
        super.setup(...arguments);
        this.data.availableSlots = [];
        this._availableSlotsCache = new Cache(
            (data) => this.fetchAvailableSlots(data),
            (data) => `${serializeDateTime(data.range.start)},${serializeDateTime(data.range.end)}`
        );
    }

    // Do not display any user activity in the appointment attendee calendar.
    get userActivitiesEnabled() {
        return false;
    }

    async updateData(data) {
        await super.updateData(data);
        data.availableSlots = await this._availableSlotsCache.read(data);
    }

    fetchAvailableSlots(data) {
        if (
            !["day", "week"].includes(this.scale) ||
            this.meta.context.active_model !== "appointment.type" ||
            !this.meta.context.active_id
        ) {
            return [];
        }

        return this.orm.call("appointment.type", "calendar_get_available_slots", [
            this.meta.context.active_id,
            serializeDateTime(data.range.start),
            serializeDateTime(data.range.end),
        ]);
    }
}



/**
 * Appointment slot editor - data overview
 *
 * The slot editor lets a user edit the availability slots of one of their appointment
 * types directly from the attendee calendar.
 *
 * `env.calendarState.mode`:
 *  - "default": regular calendar
 *  - "slots-creation": drag to create slots
 *
 * `model.data` are things that are fetched for every full data reload
 * `model.data.slots`: values of slots of the appointment type being edited.
 * `model.data.userAppointmentsData`: list of appointment types available in the "Booking Pages" list.
 *
 * `model.selectedAppointmentTypeId`: id of the appointment selected in the sidebar which should be synced
 * with the default appointment in context. Setting this highlights events of this appointment type and
 * sets it as the appointment type for events created while it is selected.
 *
 * `model.slotsAppointmentData`: values of the appointment type being edited, `undefined` when not editing.
 * This if fetched when switching which appointment is being edited, mostly to determine how slots should be generated and their values.
 *
 * `model.sidebarAppointmentData`: list of appointments actually shown in the "Booking Pages" list.
 * This data lives purely in local storage to determine which appointment types to list in the sidebar
 */

patch(AttendeeCalendarModel.prototype, {
    /**
     * @override
     */
    setup(params) {
        // always fetch those fields as they'll be used by this model
        const extraFields = ["appointment_type_id"];
        params.fieldNames = unique(params.fieldNames.concat(extraFields));
        super.setup(...arguments);
        this.data.userAppointmentsData = proxy(new Map());
        this.data.slots = {};
        const context = params.context || this.meta.context || {};
        // reactive attribute to represent which appointment type is highlighted.
        // if any, should be kept in sync with the context default for consistency.
        this.selectedAppointmentTypeId = signal(context.default_appointment_type_id);
        // selection overridden when entering edition, to be restored once edition ends.
        // `false` means there is nothing to restore.
        this.selectedAppointmentTypeIdBeforeEdition = false;
        // Relevant data of the appointment being edited in view, such as: id, duration and invite url
        // See `_updateSlotsAppointment` for the exact structure
        this.slotsAppointmentData = signal(undefined);
        // indicates if the appointment was loaded once, to know whether calendar_editing_custom_appointment_id should be used
        // if that context key is set, that appointment should be set as the appointment being edited at load time.
        // This is used to immediately enable edit mode when clicking the "slots" smart button in the appointment form.
        this.wasSlotsAppointmentLoaded = false;
        // keep the original default so we know to keep it in the sidebar list data
        // this implies that only the "edit appointment" button should be shown instead of the list
        this.originalDefaultAppointmentTypeId = context.default_appointment_type_id;
    },

    async _updateSlotsAppointment(appointmentTypeId) {
        this.wasSlotsAppointmentLoaded = true;
        if (!appointmentTypeId) {
            this.slotsAppointmentData.set(undefined);
            return;
        }
        const appointmentInfo = await rpc(
            "/appointment/appointment_type/get_calendar_slot_editor_info",
            {
                appointment_type_id: appointmentTypeId,
                ...this._getInviteParams(),
            }
        );
        const appointmentData = {
            ...appointmentInfo.appointment_type,
            // booking window for punctual appointment types
            startDatetime: appointmentInfo.appointment_type.start_datetime
                ? deserializeDateTime(appointmentInfo.appointment_type.start_datetime)
                : null,
            endDatetime: appointmentInfo.appointment_type.end_datetime
                ? deserializeDateTime(appointmentInfo.appointment_type.end_datetime)
                : null,
            url: appointmentInfo.invite_url,
        };
        this.slotsAppointmentData.set(appointmentData);
    },

    /**
     * Editor-only slot duration (in hours) for non-recurring slots.
     * Defaults to 0 minutes, aka no splitting.
     */
    getLocalStorageDuration(appointmentId) {
        let localData;
        try {
            localData = JSON.parse(
                localStorage.getItem(`appointment.slot.editor.data.${appointmentId}`)
            );
        } catch {
            localData = null;
        }
        return localData?.appointmentDuration ?? 0;
    },

    /**
     * Ensure we force the week view
     * @override
     */
    async load(params = {}) {
        const scale = params.scale || this.meta.scale;
        // if opened from an appointment, editing will start immediately and week view should be used
        if (
            !this.wasSlotsAppointmentLoaded &&
            params.context?.calendar_editing_custom_appointment_id &&
            scale !== "week"
        ) {
            params.scale = "week";
        }
        const context = params.context || this.meta.context || {};
        // initialize selection based on original context
        if (this.originalDefaultAppointmentTypeId === undefined) {
            this.originalDefaultAppointmentTypeId = context.default_appointment_type_id || false;
            this.selectedAppointmentTypeId.set(context.default_appointment_type_id);
        }
        return super.load(params);
    },

    /**
     * @override
     */
    async updateData(data) {
        // set the default edition appointment first as the search domains depends on it
        if (
            !this.wasSlotsAppointmentLoaded &&
            this.meta.context.calendar_editing_custom_appointment_id
        ) {
            await this._updateSlotsAppointment(
                this.meta.context.calendar_editing_custom_appointment_id
            );
        }
        await Promise.all([super.updateData(data), this.updateAllAppointmentData(data)]);
    },

    async updateAllAppointmentData(data) {
        if (data === undefined) {
            data = this.data;
        }
        return Promise.all([
            this.updateCustomSlotData(data),
            this.updateUserAppointmentsData(data),
        ]);
    },

    async updateCustomSlotData(data) {
        const appointmentData = this.slotsAppointmentData();
        if (!this.slotsAppointmentData()) {
            data.slots = {};
            return;
        }

        const domain = [["appointment_type_id", "=", appointmentData.id]];

        const slots = await this.orm.webSearchRead("appointment.slot", domain, {
            specification: {
                slot_type: {},
                start_datetime: {},
                end_datetime: {},
                allday: {},
                weekday: {},
                start_hour: {},
                end_hour: {},
                appointment_type_id: { fields: { name: {} } },
            },
        });

        data.slots = {};
        for (const slot of slots.records) {
            const slotVals = {
                ...slot,
                colorIndex: 2,
                slotId: slot.id,
            };
            if (slot.slot_type === "unique") {
                slotVals.start = deserializeDateTime(slot.start_datetime);
                slotVals.end = deserializeDateTime(slot.end_datetime);
                slotVals.isAllDay = slot.allday;
            }
            data.slots[slot.id] = slotVals;
        }
    },

    async updateUserAppointmentsData(data) {
        data = data ?? this.data;

        // add some ids that we'll definitely want even if they don't match the "user appointment" domain
        const forcedIds = [
            this.slotsAppointmentData()?.id, // we always want details for currently edited for the sidebar options
            this.meta.context.calendar_editing_custom_appointment_id, // in case it's not loaded yet
            this.meta.context.default_appointment_type_id, // we always want to be able to enter edition mode for the default type
            this.originalDefaultAppointmentTypeId, // always show the original default so it can be reselected
        ].filter(Boolean);

        const appointmentValues = await this.orm.webSearchRead(
            "appointment.type",
            [
                "|",
                "&",
                ["id", "in", forcedIds],
                ["active", "in", [true, false]],
                "&",
                "&",
                "&",
                "&",
                // must be specified since active is in domain
                ["active", "=", true],
                ["schedule_based_on", "=", "users"],
                ["staff_user_ids", "in", [user.userId]],
                ["category", "!=", "anytime"],
                // for custom slots, only pick those ending within the last X weeks/days to avoid clutter
                // from "one-time" appointments, also avoiding those with no slots at all
                "|",
                "&",
                "&",
                ["category", "=", "custom"],
                ["slot_ids", "!=", false],
                [
                    "slot_ids",
                    "any",
                    [
                        [
                            "end_datetime",
                            ">",
                            serializeDateTime(
                                luxon.DateTime.now().minus(
                                    APT_SIDEPANEL_LIST_PAST_FLEXIBLE_DISPLAY_LIMIT
                                )
                            ),
                        ],
                    ],
                ],
                ["category", "!=", "custom"],
            ],
            {
                specification: {
                    name: {},
                    category: {},
                    category_slot_scheduling: {},
                    user_can_manage_slots: {},
                },
            }
        );
        // use map to preserve ordering, update inplace to preserve proxy
        data.userAppointmentsData.clear();
        for (const appointment of appointmentValues.records) {
            data.userAppointmentsData.set(appointment.id, appointment);
        }
    },

    async setSelectedAppointmentTypeId(appointmentTypeId) {
        if (appointmentTypeId) {
            this.selectedAppointmentTypeId.set(appointmentTypeId);
        } else {
            this.selectedAppointmentTypeId.set(undefined);
        }
    },

    /**
     * Set the current appointment type being edited and refresh the view.
     */
    async setEditingAppointmentId(appointmentTypeId) {
        const params = appointmentTypeId && (!this.meta || this.meta.scale !== "week")
            ? { scale: "week" }
            : {};
        if (appointmentTypeId && appointmentTypeId !== this.selectedAppointmentTypeId()) {
            // editing slots = selecting it as default
            this.selectedAppointmentTypeIdBeforeEdition = this.selectedAppointmentTypeId();
            this.setSelectedAppointmentTypeId(appointmentTypeId);
        } else if (!appointmentTypeId && this.selectedAppointmentTypeIdBeforeEdition !== false) {
            // restoring pre-edition selection after edition
            this.setSelectedAppointmentTypeId(this.selectedAppointmentTypeIdBeforeEdition);
            this.selectedAppointmentTypeIdBeforeEdition = false;
        }
        // reload even if unchanged, as it might have changed since; a full load
        // is required as entering/leaving edition changes the events domain
        await this._updateSlotsAppointment(appointmentTypeId);
        await this.load(params);
        this.notify();
    },

    /**
     * @override
     */
    makeContextDefaults(rawRecord) {
        const context = super.makeContextDefaults(rawRecord);
        if (this.selectedAppointmentTypeId()) {
            context.default_appointment_type_id = this.selectedAppointmentTypeId();
        } else if ("default_appointment_type_id" in context) {
            delete context.default_appointment_type_id;
        }
        return context;
    },

    /**
     * @override
     * This method uses the value of "default_duration" in the context to set the end if it is not yet
     * defined, as it is the case when users click on the calendar. At the opposite, when the end is
     * already set, as it is the case when users drew slots in the calendar, "default_duration" is removed
     * from the context to avoid computing again the value of the end using the appointment type duration.
     */
    buildRawRecord(partialRecord, options) {
        if ("default_duration" in this.meta.context && "default_appointment_type_id" in this.meta.context) {
            if (partialRecord.end && partialRecord.end.isValid) {
                delete this.meta.context["default_duration"];
            } else if (partialRecord.start && !partialRecord.isAllDay) {
                partialRecord.end = partialRecord.start.plus({ hours: this.meta.context.default_duration });
            }
        }
        return super.buildRawRecord(...arguments);
    },

    processPartialSlotRecord(record) {
        let defaultDuration = 30;
        const appointmentData = this.slotsAppointmentData();
        const localStorageDuration = this.getLocalStorageDuration(appointmentData.id);
        if (appointmentData.category === "custom" && localStorageDuration) {
            defaultDuration = localStorageDuration * 60;
        } else if (appointmentData.appointment_duration) {
            defaultDuration = appointmentData.appointment_duration * 60;
        }

        if (!record.end || !record.end.isValid) {
            if (record.isAllDay) {
                record.end = record.start;
            } else {
                record.end = record.start.plus({ minutes: defaultDuration });
            }
        }
    },

    async createSlot(record) {
        return this.createSlots([record]);
    },

    _slotCreateVals(appointment, record) {
        this.processPartialSlotRecord(record);
        if (appointment.category_slot_scheduling !== "weekly") {
            return {
                appointment_type_id: appointment.id,
                start_datetime: serializeDateTime(record.start),
                end_datetime: serializeDateTime(record.end),
                allday: record.isAllDay,
                slot_type: "unique",
            };
        }
        // Start and end are relative to the appointment tz, values are assumed valid after conversion
        const start = record.start.setZone(appointment.appointment_tz);
        const end = record.end.setZone(appointment.appointment_tz);
        // an end falling exactly on midnight is 24:00 of the previous day (stored as end_hour 0),
        // so it still belongs to the start's day rather than spilling into the next one
        const endWeekday = end.equals(end.startOf("day"))
            ? end.minus({ days: 1 }).weekday
            : end.weekday;
        if (start.weekday !== endWeekday) {
            throw new Error("Cannot create a slot over multiple days.");
        }
        return {
            appointment_type_id: appointment.id,
            weekday: String(start.weekday),
            start_hour: start.hour + start.minute / 60,
            end_hour: end.hour + end.minute / 60,
            slot_type: "recurring",
        };
    },

    async createSlots(records) {
        const appointmentData = this.slotsAppointmentData();
        if (!appointmentData) {
            return;
        }
        const valsList = records.map((record) => this._slotCreateVals(appointmentData, record));
        try {
            await this.orm.create("appointment.slot", valsList);
        } finally {
            await this.updateAllAppointmentData();
            this.notify();
        }
    },

    async updateSlot(eventRecord, extraSlotRecords = []) {
        const appointmentData = this.slotsAppointmentData();
        this.processPartialSlotRecord(eventRecord);
        let vals;
        // as recurring slots inherently depend on the timezone of the appointment
        // we need to convert them manually
        if (eventRecord.slotType === "recurring") {
            const start = eventRecord.start.setZone(appointmentData.appointment_tz);
            const end = eventRecord.end.setZone(appointmentData.appointment_tz);
            vals = {
                weekday: String(start.weekday),
                start_hour: start.hour + start.minute / 60,
                end_hour: end.hour + end.minute / 60,
            };
        } else {
            vals = {
                start_datetime: serializeDateTime(eventRecord.start),
                end_datetime: serializeDateTime(eventRecord.end),
                allday: eventRecord.isAllDay,
            };
        }
        try {
            await this.orm.write("appointment.slot", [eventRecord.slotId], vals);
            // extending a slot may split it into several back-to-back subslots:
            // the original slot becomes the first one, the rest are created
            if (extraSlotRecords.length) {
                await this.orm.create(
                    "appointment.slot",
                    extraSlotRecords.map((record) => this._slotCreateVals(appointmentData, record))
                );
            }
        } finally {
            await this.updateAllAppointmentData();
            this.notify();
        }
    },

    async removeSlot(slotId) {
        try {
            await this.orm.unlink("appointment.slot", [slotId]);
        } finally {
            await this.updateAllAppointmentData();
            this.notify();
        }
    },

    // CONTEXT HELPERS

    /**
     * Context to pass to routes creating an invite.
     * Overridden in modules that need to somehow propagate values to invites
     */
    _getInviteParams() {
        return {};
    },
});
