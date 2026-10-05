import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";
import { deserializeDateTime } from "@web/core/l10n/dates";
import { rpc } from "@web/core/network/rpc";
import { user } from "@web/core/user";
import { range } from "@web/core/utils/numbers";
import { _t } from "@web/core/l10n/translation";

const { DateTime } = luxon;

export class appointmentSlotSelect extends Interaction {
    static selector = ".o_appointment_info";
    dynamicContent = {
        _root: {
            "t-att-class": () => ({
                "o_appointment_info_loading": this.isLoadingSlots,
            }),
        },
        "select[name='timezone']": {
            "t-on-change": this.onChangeTimezone,
        },
        "select[id='resourceCapacity']": {
            "t-on-change": this.onRefresh,
        },
        ".o_js_calendar_navigate": {
            "t-on-click": this.onCalendarNavigate,
        },
        ".o_appointment_calendar": {
            "t-att-class": () => ({
                "o_appointment_calendar_dropdown_closed": !this.dateDropdownIsOpen,
            })
        },
        ".o_appointment_entity_card": {
            "t-on-click": this.onClickEntityCard,
            "t-att-class": (el) => ({
                "o_appointment_entity_card_selected active text-primary": el === this.selectedEntityEl,
            }),
        },
        ".o_appointment_entity_card_selection": {
            "t-att-class": () => ({
                "d-none": !this.entityDropdownIsOpen,
            })
        },
        ".o_slot_day": {
            "t-on-click": this.onClickDaySlot,
            "t-att-class": (el) => ({
                "active text-primary": el === this.selectedDateEl,
            }),
        },
        ".o_slot_hours": {
            "t-on-click": this.onClickHoursSlot,
            "t-att-class": (el) => ({
                "active text-primary": el === this.selectedSlotEl,
            })
        },
        "button[name='entityDropdownBtn']": {
            "t-on-click": this.onClickEntityDropdownBtn,
        },
        "button[name='dateDropdownBtn']": {
            "t-on-click": this.onClickDateDropdownBtn,
            "t-out": () => this.dateDropdownBtnContent,
            "t-att-title": () => this.dateDropdownBtnContent,
            "t-att-disabled": () => !this.isLoadingSlots && !this.firstDayEl,
        },
        "button[name='submitSlotInfoSelected']": {
            "t-on-click": this.onClickConfirmSlot,
            "t-att-class": () => ({
                "d-none": this.isLoadingSlots || !this.selectedSlotEl || (this.confirmOnEntity && !this.selectedEntityEl),
            }),
        },
        "#next_available_slot": {
            "t-on-click": this.selectFirstAvailableMonth,
        },
        ".o_appointment_close_upcoming_appointment_alert": {
            "t-on-close.bs.alert": this.onClickCloseUpcomingAppointmentAlert,
        },
        ".o_appointment_timezone_selection": {
            "t-att-class": () => ({
                "d-none": this.isLoadingSlots || !this.firstDayEl,
            }),
        }
    };

    setup() {
        this.slotsListEl = this.el.querySelector("#slotsList");
        this.resourceSelectionEl = this.el.querySelector("#resourceSelection");
        this.firstDayEl = this.el.querySelector(".o_slot_day");

        // Appointment Data
        this.appointmentTypeId = this.el.querySelector("input[name='appointment_type_id']").value;
        this.appointmentTypeSlug = this.el.querySelector("input[name='appointment_type_slug']").value;
        this.categorySlotScheduling = this.el.querySelector("input[name='category_slot_scheduling']").value;
        this.isAppointmentActive = this.el.querySelector("input[name='active']").value;
        this.isAutoAssign = this.el.querySelector("input[name='is_auto_assign']").value;
        this.isDateFirst = this.el.querySelector("input[name='is_date_first']").value;
        this.isReschedule = this.el.querySelector("input[name='is_reschedule']").value;
        this.scheduleBasedOn = this.el.querySelector("input[name='schedule_based_on']").value;
        this.showAvatars = this.el.querySelector("input[name='show_avatars']").value;

        // Invite data
        this.appointmentsCount = parseInt(this.el.querySelector("input[name='appointments_count']").value);
        this.filterAppointmentTypeIds = this.el.querySelector("input[name='filter_appointment_type_ids']").value;
        this.filterResourceIds = this.el.querySelector("input[name='filter_resource_ids']").value;
        this.filterUserIds = this.el.querySelector("input[name='filter_staff_user_ids']").value;
        this.inviteToken = this.el.querySelector("input[name='invite_token']").value;

        // Entity (resource or user) and capacity
        this.askedCapacity = this.el.querySelector("input[name='asked_capacity']").value;
        this.entityDropdownIsOpen = false;
        this.selectedEntityEl = undefined;
        this.resourceSelectedId = this.el.querySelector("input[name='resource_selected_id']").value;
        this.useAnyEntity = this.el.querySelector("input[name='use_any_entity']").value;
        this.userSelectedId = this.el.querySelector("input[name='user_selected_id']").value;

        // Date & slot
        this.selectedDateEl = undefined;
        this.selectedSlotEl = undefined;

        // TZ
        this.selectedTimezone = this.el.querySelector("input[name='initial_timezone']").value;

        // Calendar dropdown and rendering
        this.dateDropdownBtnContent = '-';
        this.dateDropdownIsOpen = false;
        this.formattedDays = JSON.parse(this.el.querySelector("input[name='formatted_days']").value || '[]');

        // Loading
        this.isLoadingSlots = true;
        this.noValidEntities = false;

        // Confirmation logic
        this.confirmOnEntity = !this.isAutoAssign && this.isDateFirst;
        this.confirmOnHours = this.isAutoAssign || !this.isDateFirst;
    }

    willStart() {
        (async () => {
            const initialData = await rpc(
                `/appointment/${this.appointmentTypeId}/get_availability_data`,
                {
                    asked_capacity: this.askedCapacity,
                    invite_token: this.inviteToken,
                    is_first_loading: true,
                    filter_appointment_type_ids: this.filterAppointmentTypeIds,
                    filter_staff_user_ids: this.filterUserIds,
                    filter_resource_ids: this.filterResourceIds,
                    resource_selected_id: this.resourceSelectedId,
                    staff_user_id: this.userSelectedId,
                    timezone: this.selectedTimezone,
                    use_any_entity: this.useAnyEntity,
                }
            );

            if (Object.keys(initialData).length === 0) {
                this.noValidEntities = true;
                this.isLoadingSlots = false;
                await this.updateSlotAvailability(0);
                return;
            }

            const { max_possible_capacity, initial_capacity, initial_selected_entity_id } = initialData;
            this.maxPossibleCapacity = max_possible_capacity;
            if (initial_selected_entity_id) {
                this.selectedEntityEl = this.el.querySelector(
                    `.o_appointment_entity_card[data-entity-id="${initial_selected_entity_id}"]`)
            } else {
                this.selectedEntityEl = this.el.querySelector(
                    '.o_appointment_entity_card[data-use-any-entity="1"]')
            }
            this.updateEntityDropdown();

            this.renderCalendar(initialData);
            this._updateResourceCapacityOptions(initial_capacity);

            this.firstDayEl?.click();
            this.isLoadingSlots = false;
            await this.updateSlotAvailability(initial_capacity);

            // Display the calendar when no other dropdown is present
            if (
                this.firstDayEl
                && !this.el.querySelector("select[name='resourceCapacity']")
                && !this.el.querySelector("button[name='entityDropdownBtn']")
            ) {
                this.dateDropdownIsOpen = true;
                this.updateContent();
            }
        })();
    }

    start() {
        // Add listener on the page restoration from the bfcache.
        const boundOnNavigationBack = this._onNavigationBack.bind(this);
        this.addListener(window, "pageshow", boundOnNavigationBack);
    }

    /**
     * Re-enable the page when the page is restored from the bfcache.
     *
     * @param {PageTransitionEvent} event - The pageshow event.
     * @private
     */
    _onNavigationBack(event) {
        if (event.persisted) {
            this.el.classList.remove("o_appointment_disable");
        }
    }

    /**
     * Finds the first day with an available slot, replaces the currently shown month and
     * click on the first date where a slot is available.
     */
    selectFirstAvailableMonth() {
        const firstMonthEl = this.firstDayEl.closest(".o_appointment_month");
        const currentMonthEl = document.querySelector(".o_appointment_month:not(.d-none)");
        currentMonthEl.classList.add("d-none");
        currentMonthEl.querySelector("table").classList.remove("d-none");
        currentMonthEl.querySelector(".o_appointment_no_slot_month_helper").remove();
        firstMonthEl.classList.remove("d-none");
        this.slotsListEl.replaceChildren();
        this.selectDaySlot(this.firstDayEl, false);
        this.dateDropdownIsOpen = true;
        this.entityDropdownIsOpen = false;
    }

    /**
     * Replaces the content of the calendar month with the no month helper.
     * Renders and appends its template to the element given as argument.
     * - monthEl: the month div to which we append the helper.
     */
    renderNoAvailabilityForMonth(monthEl) {
        const firstAvailabilityDate = this.firstDayEl.getAttribute("id");
        monthEl.querySelectorAll("table").forEach((tableEl) => tableEl.classList.add("d-none"));
        monthEl.querySelector(".o_appointment_month_loader").classList.add("d-none");

        this.renderAt("Appointment.appointment_info_no_slot_month", {
            firstAvailabilityDate: DateTime.fromISO(firstAvailabilityDate).toLocaleString({
                day: "numeric",
                weekday: "long",
                month: "long",
                year: "numeric",
            }),
            selectedEntityName: this.selectedEntityEl?.dataset?.entityName,
        }, monthEl);

        this.dateDropdownIsOpen = true;
        this.entityDropdownIsOpen = false;
        this.dateDropdownBtnContent = '-';
    }

    _updateResourceCapacityOptions(initialCapacity) {
        const capacitySelect = document.querySelector("select[name='resourceCapacity']");
        if ((this.isAutoAssign || this.isDateFirst || this.selectedEntityEl) && !!capacitySelect) {
            const previousCapacitySelected = parseInt(capacitySelect.value);
            const targetCapacity = initialCapacity || previousCapacitySelected;
            capacitySelect.replaceChildren();
            this.renderAt(
                "appointment.resources_capacity_options",
                {
                    asked_capacity: targetCapacity && (targetCapacity <= this.maxPossibleCapacity)
                        ? targetCapacity
                        : false,
                    max_capacity: this.maxPossibleCapacity,
                    noAvailability: !this.firstDayEl,
                    range,
                },
                capacitySelect
            );
        }
    }

    /**
     * Handle unavailability messages if needed, except for appointment_info_no_slot_month.
     * If capacity is managed, suggest changing party size if no slot and currently > 1.
     * Also handle missing configuration and upcoming appointment alert messages
     * - targetCapacity: integer, capacity selected by user before loading / refreshing
     */
    async updateSlotAvailability(targetCapacity) {
        const noCapacityEl = this.el.querySelector(".o_appointment_no_capacity");
        if (!this.firstDayEl) { // No slot available
            const resourceCapacityEl = this.el.querySelector("select[name='resourceCapacity']");
            if (!resourceCapacityEl) {
                const noSlotOverallEl = this.el.querySelector(".o_appointment_no_slot_overall_helper");
                noSlotOverallEl.replaceChildren();
                this.el.querySelector("#calendar_wrapper")?.replaceChildren();
                this.renderAt("Appointment.appointment_info_no_slot", {
                    active: this.isAppointmentActive,
                    appointmentsCount: this.appointmentsCount,
                    selectedEntityName: this.selectedEntityEl?.dataset?.entityName,
                }, noSlotOverallEl);

            } else {
                noCapacityEl?.replaceChildren();
                // When capacity is 0 ('-' option), the current entity selection has no
                // availability for previous asked capacity. If target capacity is 1, the selected
                // entity has no availability at all. We can display the appropriate helper message
                if ((targetCapacity || 1) === 1) {
                    this.renderAt("Appointment.appointment_info_no_slot", {
                        active: this.isAppointmentActive,
                        appointmentsCount: this.appointmentsCount,
                        selectedEntityName: this.selectedEntityEl?.dataset?.entityName,
                    }, noCapacityEl);
                } else {
                    this.renderAt("Appointment.appointment_info_no_capacity", {}, noCapacityEl);
                }
                // As no date is available, we force the calendar to be hidden.
                this.dateDropdownIsOpen = false;
            }
        } else {
            noCapacityEl?.replaceChildren();
        }

        this.el.querySelector(".o_appointment_missing_configuration")?.classList.remove("d-none");
        // Check upcoming appointments
        const allAppointmentsToken = JSON.parse(localStorage.getItem("appointment.upcoming_events_access_token")) || [];
        const ignoreUpcomingEventUntil = localStorage.getItem("appointment.upcoming_events_ignore_until");
        if (!this.el.querySelector('.o_appointment_reschedule') &&
            !this.el.querySelector('.o_appointment_forced_staff_user_assigned') &&
            (!ignoreUpcomingEventUntil || deserializeDateTime(ignoreUpcomingEventUntil) < DateTime.utc()) &&
            (allAppointmentsToken.length !== 0 || user.userId !== false)
        ) {
            const upcomingAppointmentData = await this.waitFor(
                rpc("/appointment/get_upcoming_appointments", {
                    calendar_event_access_tokens: allAppointmentsToken,
                })
            );
            this.protectSyncAfterAsync(() => {
                if (upcomingAppointmentData) {
                    if (!localStorage.getItem('appointment.hide_upcoming_appointment_alert')){
                        const upcomingFormattedStart = deserializeDateTime(
                            upcomingAppointmentData.next_upcoming_appointment.start
                        ).setZone(this.selectedTimezone).toLocaleString(DateTime.DATETIME_MED_WITH_WEEKDAY);
                        
                        this.el.querySelector(".o_appointment_upcoming_appointment_alert").replaceChildren(); 
                        this.renderAt("Appointment.appointment_info_upcoming_appointment", {
                            appointmentTypeName: upcomingAppointmentData.next_upcoming_appointment.appointment_type_id[1],
                            appointmentStart: upcomingFormattedStart,
                            appointmentToken: upcomingAppointmentData.next_upcoming_appointment.access_token,
                            partnerId: upcomingAppointmentData.next_upcoming_appointment.appointment_booker_id[0],
                        }, this.el.querySelector(".o_appointment_upcoming_appointment_alert"));

                        if (user.userId === false) {
                            localStorage.setItem("appointment.upcoming_events_access_token", JSON.stringify(upcomingAppointmentData.valid_access_tokens));
                        }
                    } else {
                        localStorage.removeItem("appointment.upcoming_events_access_token");
                    }
                }
            })();
        }
    }

    /**
     * Navigate between the months available in the calendar displayed
     */
    async onCalendarNavigate(ev) {
        const parentEl = this.el.querySelector(".o_appointment_month:not(.d-none)");
        let monthID = parseInt(parentEl.getAttribute("id").split("-")[1]);
        monthID += ev.currentTarget.getAttribute("id") === "nextCal" ? 1 : -1;
        parentEl.querySelectorAll("table").forEach((table) => table.classList.remove("d-none"));
        parentEl
            .querySelectorAll(".o_appointment_no_slot_month_helper")
            .forEach((element) => element.remove());
        parentEl.classList.add("d-none");
        let monthEl = this.el.querySelector(`div#month-${monthID}`);
        monthEl.classList.remove("d-none");
        this.selectedDateEl = undefined;
        this.selectedSlotEl = undefined;
        this.dateDropdownBtnContent = '-';
        this.slotsListEl.replaceChildren();
        this.resourceSelectionEl?.replaceChildren();

        const monthTableEl = monthEl.querySelector("table");
        const monthLoaderEl = monthEl.querySelector(".o_appointment_month_loader");
        monthTableEl.classList.add("d-none");
        if (monthLoaderEl) {
            monthLoaderEl.classList.remove("d-none");
        }
        await this.onRefresh();
        this.dateDropdownIsOpen = true;
        this.entityDropdownIsOpen = false;
    }

    async onChangeTimezone(ev) {
        this.selectedTimezone = ev.currentTarget.value;
        await this.onRefresh();
    }

    onClickDateDropdownBtn() {
        this.dateDropdownIsOpen = !this.dateDropdownIsOpen;
        this.entityDropdownIsOpen = this.entityDropdownIsOpen && !this.dateDropdownIsOpen;
    }

    onClickDaySlot(ev) {
        this.selectDaySlot(ev.currentTarget);
    }

    selectDaySlot(daySlotEl, closeDropdown = true){
        if (daySlotEl === this.selectedDateEl) {
            return;
        }
        this.selectedDateEl = daySlotEl;

        const slotDate = daySlotEl.dataset.slotDate;
        const daySlotClasses = [...daySlotEl.classList];

        if (daySlotClasses.includes("o_today")) {
            this.dateDropdownBtnContent = _t("Today");
        } else if (daySlotClasses.includes("o_tomorrow")) {
            this.dateDropdownBtnContent = _t("Tomorrow");
        } else {
            this.dateDropdownBtnContent = DateTime.fromISO(slotDate).toLocaleString({
                day: "numeric",
                weekday: "long",
                month: "long",
            });
        }

        const slots = JSON.parse(this.selectedDateEl.dataset.availableSlots);
        const resourceId =
            this.scheduleBasedOn === "resources" && !this.isAutoAssign && !this.isDateFirst
            ? parseInt(this.selectedEntityEl?.dataset?.entityId)
            : undefined;
        const resourceCapacity = this.el.querySelector("select[name='resourceCapacity']")?.value;
        let commonUrlParams = new URLSearchParams(window.location.search);
        // Clear url parameters. If for instance the slot is not available anymore on details submission,
        // the user would be brought back to this screen with previously selected values. We do not want
        // them to interfere, hence we clear them here.
        [
            "allday",
            "available_resource_ids",
            "date_time",
            "duration",
            "resource_selected_id",
            "staff_user_id",
            "use_any_entity"
        ].forEach((urlParam) => commonUrlParams.delete(urlParam));

        if (resourceCapacity) {
            commonUrlParams.set("asked_capacity", encodeURIComponent(resourceCapacity));
        }
        if (resourceId) {
            commonUrlParams.set("resource_selected_id", encodeURIComponent(resourceId));
        }

        this.slotsListEl.replaceChildren();
        this.renderAt("appointment.slots_list", {
            categorySlotScheduling: this.categorySlotScheduling,
            commonUrlParams: commonUrlParams,
            scheduleBasedOn: this.scheduleBasedOn,
            slotDate: DateTime.fromISO(slotDate).toLocaleString({
                day: "numeric",
                weekday: "long",
                month: "long",
                year: "numeric",
            }),
            slots: slots,
            getAvailableResources: (slot) => {
                return this.scheduleBasedOn === "resources"
                    ? JSON.stringify(slot["available_resources"])
                    : false;
            },
            getAvailableUsers: (slot) => {
                return this.scheduleBasedOn === "users"
                    ? JSON.stringify(slot["available_staff_users"])
                    : false;
            },
        }, this.slotsListEl);
        this.slotsListEl = this.el.querySelector("#slotsList");
        this.resourceSelectionEl?.classList.add("d-none");

        // Reset selections
        if (this.isDateFirst) {
            this.selectedEntityEl = undefined;
        }
        this.selectedSlotEl = undefined;

        // Select first available slot
        const firstAvailableSlotEl = this.slotsListEl?.querySelector(".o_slot_hours");
        if (!!firstAvailableSlotEl) {
            this.selectHoursSlot(firstAvailableSlotEl, false);
        }

        if (closeDropdown) {
            this.dateDropdownIsOpen = false;
        }
    }

    async onClickEntityCard(ev) {
        if (ev.currentTarget === this.selectedEntityEl) {
            return;
        }
        this.selectedEntityEl = ev.currentTarget;

        if (!this.isDateFirst) {
            this.updateEntityDropdown();
            await this.onRefresh();
            this.entityDropdownIsOpen = false;
        } else if (!this.isReschedule && this.confirmOnEntity) {
            this.confirmSlotSelection();
        }
    }

    onClickEntityDropdownBtn() {
        this.entityDropdownIsOpen = !this.entityDropdownIsOpen;
        this.dateDropdownIsOpen = this.dateDropdownIsOpen && !this.entityDropdownIsOpen;
    }

    onClickHoursSlot(ev) {
        this.selectHoursSlot(ev.currentTarget);
    }

    selectHoursSlot(hoursSlotEl, confirmSlotSelection = true) {
        if (hoursSlotEl === this.selectedSlotEl) {
            return;
        }
        this.selectedSlotEl = hoursSlotEl;

        // No additional selection needed
        if (this.confirmOnHours) {
            if (!this.isReschedule && confirmSlotSelection) {
                this.confirmSlotSelection();
            }
            return;
        }

        // Update the resource list for manual selection
        const availableResources = hoursSlotEl.dataset.availableResources
            ? JSON.parse(hoursSlotEl.dataset.availableResources)
            : undefined;
        const availableStaffUsers = hoursSlotEl.dataset.availableStaffUsers
            ? JSON.parse(hoursSlotEl.dataset.availableStaffUsers)
            : undefined;
        const availableEntities = this.scheduleBasedOn === 'resources'
            ? availableResources
            : availableStaffUsers;

        this.resourceSelectionEl?.replaceChildren();
        this.renderAt("appointment.resources_list", {
            appointmentTypeId: this.appointmentTypeId,
            availableEntities,
            scheduleBasedOn: this.scheduleBasedOn,
            showAvatars: this.showAvatars,
        }, this.resourceSelectionEl);

        if (this.isDateFirst && !this.isAutoAssign) {
            this.selectedEntityEl = this.el.querySelector(".o_appointment_entity_card");
        }
        this.resourceSelectionEl.classList.remove("d-none");
    }

    onClickConfirmSlot(ev) {
        if (this.isReschedule) {
            this.confirmRescheduleSelection();
        } else {
            this.confirmSlotSelection();
        }
    }

    confirmSlotSelection() {
        this.el.classList.add("o_appointment_disable");
        const entityId = this.selectedEntityEl?.dataset?.entityId;
        const urlParameters = decodeURIComponent(
            this.selectedSlotEl?.dataset?.urlParameters
        );
        const url = new URL(
            `/appointment/${encodeURIComponent(this.appointmentTypeSlug)}/info?${urlParameters}`,
            location.origin);

        if (this.isAutoAssign || !this.isDateFirst) {
            if (!this.isAutoAssign && !entityId) {
                url.searchParams.set("use_any_entity", 1);
            }
        } else if (this.scheduleBasedOn === "resources") {
            const resourceCapacity =
                parseInt(this.el.querySelector("select[name='resourceCapacity']")?.value) || 1;
            let resourceIds = JSON.parse(url.searchParams.get("available_resource_ids"));
            if (
                this.isDateFirst && !this.isAutoAssign &&
                !!this.selectedEntityEl &&
                parseInt(this.selectedEntityEl?.dataset?.resourceCapacity) >= resourceCapacity
            ) {
                resourceIds = [parseInt(entityId)];
            }
            url.searchParams.set("resource_selected_id", encodeURIComponent(entityId));
            url.searchParams.set("available_resource_ids", JSON.stringify(resourceIds));
            url.searchParams.set("asked_capacity", encodeURIComponent(resourceCapacity));
        } else {
            url.searchParams.set("staff_user_id", encodeURIComponent(entityId));
        }
        document.location = url.href;
    }

    confirmRescheduleSelection() {
        const formEl = this.el.querySelector("#reschedule_form");
        const entityId = this.selectedEntityEl?.dataset?.entityId || '';
        const urlParameters = decodeURIComponent(this.selectedSlotEl?.dataset?.urlParameters);
        const searchParams = new URLSearchParams(urlParameters);
        const rescheduleVals = {
            datetime_str: searchParams.get("date_time"),
            duration_str: searchParams.get("duration"),
            allday: searchParams.get("allday") || 0,
            asked_capacity: searchParams.get("asked_capacity") || 1,
        };

        if (this.scheduleBasedOn === "resources") {
            const resourceCapacity =
                parseInt(this.el.querySelector("select[name='resourceCapacity']")?.value) || 1;
            let resourceIds = JSON.parse(searchParams.get("available_resource_ids"));
            if (
                this.selectedEntityEl &&
                this.isDateFirst &&
                !this.isAutoAssign &&
                parseInt(this.selectedEntityEl.dataset.resourceCapacity) >= resourceCapacity
            ) {
                resourceIds = [parseInt(entityId)];
            }
            rescheduleVals.resource_selected_id = entityId;
            rescheduleVals.available_resource_ids = JSON.stringify(resourceIds);
            rescheduleVals.asked_capacity = resourceCapacity;
        } else {
            rescheduleVals.staff_user_id = entityId || searchParams.get("staff_user_id");
        }
        for (const [name, value] of Object.entries(rescheduleVals)) {
            const input = formEl.querySelector(`input[name="${name}"]`);
            if (input) {
                input.value = value;
            }
        }
        formEl.submit();
    }

    /**
     * Refresh the slots info when the user modifies the timezone or the selected user.
     */
    async onRefresh(ev) {
        if (this.noValidEntities) {
            return;
        }

        this.isLoadingSlots = true;
        this.updateContent();
        const calendarEl = this.el.querySelector("#calendar_wrapper");
        if (calendarEl) {
            const daySlotSelected = this.selectedDateEl?.dataset.slotDate;
            const visibleMonth = this.el.querySelector(".o_appointment_month:not(.d-none)");
            const resourceCapacity =
                (this.el.querySelector("select[name='resourceCapacity']") &&
                    parseInt(this.el.querySelector("select[name='resourceCapacity']").value)) ||
                1;
            this.el.querySelector(".o_appointment_no_slot_overall_helper").replaceChildren();
            this.slotsListEl?.replaceChildren();
            this.selectedDateEl = undefined;
            this.selectedSlotEl = undefined;
            this.resourceSelectionEl?.replaceChildren();
            if (this.isDateFirst) {
                this.selectedEntityEl = undefined;
            }
            const staffUserID =
                this.scheduleBasedOn === 'users' && !this.isAutoAssign && !this.isDateFirst
                ? parseInt(this.selectedEntityEl?.dataset?.entityId)
                : undefined;
            const resourceID =
                this.scheduleBasedOn === 'resources' && !this.isAutoAssign && !this.isDateFirst
                ? parseInt(this.selectedEntityEl?.dataset?.entityId)
                : undefined;
            const updatedData = await rpc(
                `/appointment/${this.appointmentTypeId}/get_availability_data`,
                {
                    asked_capacity: resourceCapacity,
                    asked_month: !!visibleMonth ? [
                        parseInt(visibleMonth.dataset.monthNumber),
                        parseInt(visibleMonth.dataset.yearNumber),
                    ] : undefined,
                    invite_token: this.inviteToken,
                    filter_appointment_type_ids: this.filterAppointmentTypeIds,
                    filter_staff_user_ids: this.filterUserIds,
                    filter_resource_ids: this.filterResourceIds,
                    month_before_update: visibleMonth?.dataset.monthName,
                    resource_selected_id: resourceID,
                    staff_user_id: staffUserID,
                    timezone: this.selectedTimezone,
                }
            );
            if (updatedData) {
                const { max_possible_capacity } = updatedData;
                this.maxPossibleCapacity = max_possible_capacity;
                this.renderCalendar(updatedData);

                this.dateDropdownBtnContent = '-';

                this._updateResourceCapacityOptions();
                await this.updateSlotAvailability(resourceCapacity);

                // If possible, we kept the current month. We display the helper if it has no availability.
                const displayedMonthEl = this.el.querySelector(".o_appointment_month:not(.d-none)");
                const firstDayInMonthEl = displayedMonthEl?.querySelector(".o_slot_day");
                if (!!this.firstDayEl && !firstDayInMonthEl) {
                    this.renderNoAvailabilityForMonth(displayedMonthEl);
                }

                // Select previous selected date if possible, or first available date.
                const previousDayEl = displayedMonthEl?.querySelector(`div[data-slot-date="${daySlotSelected}"]`);
                if (firstDayInMonthEl) {
                    this.selectDaySlot(previousDayEl || firstDayInMonthEl, false);
                }
            }
        }
        this.isLoadingSlots = false;
    }

    renderCalendar(calendarData) {
        const calendarEl = this.el.querySelector("#calendar_wrapper");
        calendarEl.replaceChildren();
        this.renderAt("appointment.calendar_wrapper", {
            ...calendarData,
            formattedDays: this.formattedDays,
            isAppointmentActive: this.isAppointmentActive,
            stringifySlots: (slots) => JSON.stringify(slots),
            todayLabel: _t("Today"),
        }, calendarEl);

        // New first day
        this.firstDayEl = this.el.querySelector(".o_slot_day");
    }

    updateEntityDropdown() {
        const entityDropdownBtnEl = this.el.querySelector("button[name='entityDropdownBtn']")
        if (!entityDropdownBtnEl) {
            return;
        }

        entityDropdownBtnEl.replaceChildren();
        this.renderAt("appointment.entity_dropdown_button_card", {
            appointmentTypeId: this.appointmentTypeId,
            entityId: this.selectedEntityEl?.dataset?.entityId,
            entityName: this.selectedEntityEl?.dataset?.entityName,
            scheduleBasedOn: this.scheduleBasedOn,
            showAvatars: this.showAvatars,
            useAnyEntity: this.selectedEntityEl?.dataset?.useAnyEntity,
        }, entityDropdownBtnEl)
    }

    onClickCloseUpcomingAppointmentAlert() {
        localStorage.setItem('appointment.hide_upcoming_appointment_alert', true);
    }
}


registry
    .category("public.interactions")
    .add("appointment.appointment_select_appointment_slot", appointmentSlotSelect);

