import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { GanttRenderer } from "@web_gantt/gantt_renderer";
import { patch } from "@web/core/utils/patch";
const { DateTime } = luxon;
import { onWillStart } from "@odoo/owl";
import { AppointmentGanttPopover } from "./gantt_popover";

export class AppointmentBookingGanttRenderer extends GanttRenderer {
    static pillTemplate = "appointment.AppointmentBookingGanttRendererPill";
    static components = {
        ...GanttRenderer.components,
        Popover: AppointmentGanttPopover,
    }

    /**
     * @override
     */
    setup() {
        super.setup();
        this.orm = useService("orm");

        onWillStart(async () => {
            this.isAppointmentManager = await user.hasGroup("appointment.group_appointment_manager");
        });
    }

    /**
     * @override
     * If multiple columns have been selected, remove the default duration from the context so that
     * the stop matches the end of the selection instead of being redefined to match the appointment duration.
     */
    onCreate(rowId, columnStart, columnStop) {
        let { start } = this.getSubColumnFromColNumber(columnStart);
        let { stop } = this.getSubColumnFromColNumber(columnStop);
        ({ start, stop } = this.normalizeTimeRange(start, stop));
        const context = this.model.getDialogContext({rowId, start, stop, withDefault: true});
        if (columnStop != columnStart + this.model.metaData.scale.cellPart - 1){
            delete context['default_duration'];
        }
        this.props.create(context);
    }

    /**
     * @override
     */
    enrichPill(pill) {
        const enrichedPill = super.enrichPill(pill);
        const { record } = pill;
        if (!record.appointment_type_id) {
            return enrichedPill;
        }
        const now = DateTime.now();
        // see o-colors-complete for array of colors to index into
        let color = false;
        if (!record.active) {
            color = false;
        } else if (record.appointment_status === 'booked') {
            color = now.diff(record.start, ['minutes']).minutes > 15 ? 2 : 4;  // orange if late ; light blue if not
        } else if (record.appointment_status === 'attended') {
            color = 10;  // green
        } else if (record.appointment_status === 'no_show') {
            color = 1;  // red
        } else if (record.appointment_status === 'request' && record.start < now) {
            color = 2;  // orange (request state has info-decoration)
        } else {
            color = 8;  // blue
        }
        if (color) {
            enrichedPill._color = color;
            enrichedPill.className += ` o_gantt_color_${color}`;
        }
        return enrichedPill;
    }

    /**
     * @override
     */
    processRow() {
        const result = super.processRow(...arguments);
        const { isGroup, id: rowId } = result.rows[0];
        if (!isGroup && this.model.metaData.groupedBy.includes("partner_ids")) {
            const { partner_ids } = Object.assign({}, ...JSON.parse(rowId));
            for (const pill of this.rowPills[rowId]) {
                if (partner_ids[0] !== pill.record.partner_id.id) {
                    pill.className += " o_appointment_booking_gantt_color_grey";
                }
            }
        }
        return result;
    }

    /**
     * Patch the flow so that we will have access to the id of the partner
     * in the row the user originally clicked when writing to reschedule, as originId.
     *
     * @override
     */
    async dragPillDrop({ pill, cell, diff }) {
        let unpatch = null;
        if (this.model.metaData.groupedBy && (this.model.metaData.groupedBy[0] === "partner_ids" || this.model.metaData.groupedBy[0] === "resource_ids")) {
            const originResId = this.rows.find((row) => {
                return this.rowPills[row.id].some(
                    (rowPill) => rowPill.id === this.pills[pill.dataset.pillId].id,
                );
            })?.resId;
            unpatch = patch(this.model, {
                getSchedule() {
                    const schedule = super.getSchedule(...arguments);
                    schedule.originId = originResId;
                    return schedule;
                },
            });
        }
        const ret = super.dragPillDrop(...arguments);
        if (unpatch) {
            unpatch();
        }
        return ret;
    }

    /**
     * @override
     */
    getPopoverProps(pill) {
        const popoverProps = super.getPopoverProps(...arguments);
        popoverProps.record = pill.record;
        return popoverProps;
    }

    /**
     * @override
     */
    async undoDragDropAction(resId, dragAction, fallbackData, messages) {
        const cleanFallbackData = { ...fallbackData };
        delete cleanFallbackData?.originId;
        return await super.undoDragDropAction(resId, dragAction, cleanFallbackData, messages);
    }

    /** TOTAL ROW **/

    /**
     * @override
     * Sum on the total_capacity_reserved of bookings instead of using the count
     */
    addTo(pill, group) {
        if (!pill.record.total_capacity_reserved) {
            return false;
        }
        group.pills.push(pill);
        group.aggregateValue += pill.record.total_capacity_reserved;
        return true;
    }

    /**
     * @override
     * Only compute total row(s) when considering a single appointment type.
     * This is to avoid a mix of definitions on total_capacity_reserved:
     * When manage_capacity is true on the appointment type, it is the total
     * reserved resource_capacity. When false, it is always 1 to count as
     * an "occurence", see max_bookings field. This enables the total when
     * coming from an appointment.type, which is the default use case.
     */
    shouldComputeAggregateValues(row) {
        return this.props.context.default_appointment_type_id;
    }
}
