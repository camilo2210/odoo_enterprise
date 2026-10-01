import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { ReassignAppointmentPopup } from "../components/reassign_appointment_popup/reassign_appointment_popup";
import { _t } from "@web/core/l10n/translation";

patch(PosStore.prototype, {
    async setup() {
        await super.setup(...arguments);
        this.bookingSelectionAppointment = null;
        this.data.connectWebSocket("TABLE_BOOKING", (payload) => {
            const { command, data } = payload;
            if (!data) {
                return;
            }
            if (command === "ADDED") {
                this.models.connectNewData(data);
                this.data.synchronizeServerDataInIndexedDB(data);
            } else if (command === "REMOVED") {
                for (const calendarData of data["calendar.event"]) {
                    this.models["calendar.event"].get(calendarData.id)?.delete?.();
                }
            }
        });
    },

    /**
     * Assigns a POS table to a calendar event booking.
     * If no linked resource table is found, prompts user to select one.
     */
    async assignResourceToAppointment(appointmentId, callBack = null, opt = {}) {
        if (!this.config.module_pos_restaurant || !appointmentId) {
            return;
        }
        let appointment = this.models["calendar.event"].get(appointmentId);
        if (!appointment) {
            appointment = (await this.data.read("calendar.event", [appointmentId]))[0];
        }
        if (!appointment) {
            return;
        }

        const tableToSet = await this._startTableBookingSelection(appointment);
        if (!tableToSet) {
            return;
        }

        const resources = tableToSet.map((t) => t.appointment_resource_id);
        if (!resources.length) {
            return;
        }
        // Used ormWrite to ensure the record is updated before calling _updateTimer,
        // as _updateTimer relies on the latest calendar.event data.
        await this.data.ormWrite("calendar.event", [appointment.id], {
            resource_ids: resources.map((r) => r.id),
            total_capacity_reserved: resources.reduce((sum, r) => sum + r.capacity, 0),
        });
        // To update local data after ormWrite
        await this.data.read("calendar.event", [appointment.id]);
        opt.closeNotification?.();
        callBack?.(opt.viewMode);
    },

    /**
     * Prompts user to select table(s) on FloorScreen for an appointment.
     * Returns selected table(s) or false if cancelled.
     */
    _startTableBookingSelection(appointment) {
        const reservedCapacity =
            appointment.waiting_list_capacity || appointment.total_capacity_reserved;
        const selectedTables = [];
        const selectedTablesEle = [];
        let capacityReserved = 0;

        this.bookingSelectionAppointment = appointment;
        this.isAppointmentTransferMode = true;
        this.navigate("FloorScreen");

        const { promise, resolve } = Promise.withResolvers();

        // Cleanup and finalize selection
        const cleanupAndResolve = (selectedTable) => {
            document.removeEventListener("click", onTableClick);
            this.isAppointmentTransferMode = false;
            this.bookingSelectionAppointment = null;
            this.alert.remove();
            selectedTablesEle.forEach((tableEle) => tableEle.classList.remove("border-info"));
            resolve(selectedTable);
        };
        this.alert.add(
            _t(
                "Choose a table for %s: %s people remaining",
                appointment.attendeeName,
                reservedCapacity
            ),
            { onClose: cleanupAndResolve.bind(this, []), closable: true }
        );
        // Handle individual table selection
        const onTableClick = async (ev) => {
            // Exit if user navigated away from FloorScreen
            if (this.router.currentScreen() !== "FloorScreen" || !this.isAppointmentTransferMode) {
                cleanupAndResolve([]);
                return;
            }

            const tableElement = ev.target.closest(".table");
            if (!tableElement) {
                return;
            }

            const table = this.getTableFromElement(tableElement);
            if (!table || !table.appointment_resource_id || selectedTables.includes(table)) {
                return;
            }
            const orderOnSelectedTable = table.getOrders().find((order) => !order.finalized);
            if (orderOnSelectedTable) {
                return this.notification.add(_t("This table is occupied by an active order."), {
                    type: "warning",
                });
            }
            const remainingToAssign = reservedCapacity - capacityReserved;
            const existingAppointment = table.firstAppointment;
            // Ignore if the same appointment table is already selected.
            if (appointment.id === existingAppointment.id) {
                return this.notification.add(
                    _t("The table is already assigned to this appointment."),
                    {
                        type: "warning",
                    }
                );
            }
            // Handle table with existing appointment
            if (existingAppointment) {
                const payload = await makeAwaitable(this.dialog, ReassignAppointmentPopup, {
                    appointment,
                    existingAppointment,
                    table,
                });

                if (!payload) {
                    return;
                }
                if (payload === "swap") {
                    await this._swapAppointmentResources(appointment, existingAppointment);
                } else if (payload === "reassign") {
                    await this._reassignAppointmentResources(
                        appointment,
                        existingAppointment,
                        table
                    );
                }
            }
            tableElement.classList.add("border-info");
            selectedTablesEle.push(tableElement);

            // Table has enough capacity for remaining guests
            if (remainingToAssign <= table.appointment_resource_id.capacity) {
                cleanupAndResolve([...selectedTables, table]);
                return;
            }

            // Add table and continue selection
            capacityReserved += table.appointment_resource_id.capacity;
            selectedTables.push(table);

            this.alert.add(
                _t(
                    "Choose a table for %s: %s people remaining",
                    appointment.attendeeName,
                    remainingToAssign
                ),
                { onClose: cleanupAndResolve.bind(this, []), closable: true }
            );
        };

        document.addEventListener("click", onTableClick);
        return promise;
    },

    /**
     * Swap appointment's resources between two appointments.
     */
    async _swapAppointmentResources(sourceAppointment, destinationAppointment) {
        await this.data.callRelated("calendar.event", "swap_resources_between_events", [
            sourceAppointment.id,
            destinationAppointment.id,
            this.config.id,
        ]);
    },

    /**
     * Reassign an existing appointment's resource to a new appointment.
     */
    async _reassignAppointmentResources(sourceAppointment, destinationAppointment, table) {
        const tableResource = destinationAppointment.appointment_resource_ids.find(
            (r) => r.id === table.appointment_resource_id.id
        );
        await this.data.callRelated("calendar.event", "reassign_resources_to_event", [
            sourceAppointment.id,
            destinationAppointment.id,
            tableResource.id,
            this.config.id,
        ]);
        await this.assignResourcesAutomatically(destinationAppointment, tableResource.id);
    },
    getTotalAvailableCapacity(records) {
        return records?.length > 0
            ? records[0].data?.available_capacity || 0
            : this.config.appointment_type_id.resource_total_capacity || 0;
    },
    async assignResource(recordId, opt = {}) {
        await this.assignResourceToAppointment(recordId, this.manageBookings.bind(this), opt);
    },
    showResourceAssignNotification(record, resources, opt = {}) {
        let resId = record.id;
        if (typeof record.id === "string") {
            resId = record.resId;
            resources = resources.map((r) => r.data);
        }
        const message = resources.length
            ? _t("Assigned to %s", resources?.map((r) => r.display_name).join(", "))
            : _t("No table assigned");
        const closeNotification = this.notification.add(message, {
            type: !resources.length ? "warning" : "success",
            sticky: !resources.length,
            autocloseDelay: 7000,
            buttons: [
                {
                    name: resources.length ? _t("Change") : _t("Choose Table"),
                    onClick: () =>
                        this.assignResource(resId, {
                            closeNotification: closeNotification,
                            ...opt,
                        }),
                },
            ],
        });
    },
    async assignResourcesAutomatically(appointment, resource_id) {
        const currentResourceIds = appointment.appointment_resource_ids
            .filter((ar) => ar.id !== resource_id)
            .map((ar) => ar.id);
        await this.data.callRelated("calendar.event", "assign_available_resources_to_event", [
            appointment.id,
            this.config.id,
            resource_id,
        ]);
        const isResourceAssigned = appointment.appointment_resource_ids.some(
            (ar) => !currentResourceIds.includes(ar.id)
        );
        if (isResourceAssigned) {
            const tables = appointment.appointment_resource_ids
                .flatMap((r) => r.pos_table_ids.map((t) => t.table_number))
                .join(", ");
            this.notification.add(
                _t("%s reassigned to Tables %s", appointment.attendeeName, tables),
                {
                    type: "success",
                }
            );
            return;
        }
        this.notification.add(
            _t("Could not find a table for %s. (no resource assigned)", appointment.attendeeName),
            { type: "warning" }
        );
    },
});
