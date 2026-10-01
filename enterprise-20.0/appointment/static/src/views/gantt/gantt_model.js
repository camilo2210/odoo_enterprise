import { GanttModel } from "@web_gantt/gantt_model";
import { localStartOf } from "@web_gantt/gantt_helpers";

export class AppointmentBookingGanttModel extends GanttModel {
    /**
     * @override
     */
    load(searchParams) {
        // add some context keys to the search
        return super.load({
            ...searchParams,
            context: {
                ...searchParams.context,
                appointment_booking_gantt_show_all_resources: true,
                appointment_allow_overbooking: true, // moving things to "unassigned" in gantt is explicit enough
            }
        });
    }

    /**
     * Update the organizer of relevant events after updating attendees.
     *
     * @override
     */
    async reschedule(ids, schedule, callback) {
        if (
            !this.metaData.groupedBy ||
            this.metaData.groupedBy[0] !== "partner_ids" ||
            !schedule.partner_ids
        ) {
            return super.reschedule(...arguments);
        }

        if (!Array.isArray(ids)) {
            ids = [ids];
        }
        const idsToUpdate = this.data.records
            .filter(
                (record) =>
                    ids.includes(record.id) &&
                    ((record.partner_id?.length && schedule.originId === record.partner_id.id) ||
                        !record.partner_id?.length),
            )
            .map((record) => record.id);
        const newUserId = this.orm
            .read("res.partner", [schedule.partner_ids[0]], ["user_ids"])
            .then((result) => (result[0]?.user_ids[0] ? result[0].user_ids[0] : false));

        const result = super.reschedule(ids, schedule, async (ormWriteResult) => {
            if (idsToUpdate.length && newUserId) {
                await this.orm.write("calendar.event", idsToUpdate, {
                    user_id: await newUserId,
                });
            }
            if (callback) {
                callback(ormWriteResult);
            }
        });

        return result;
    }

    /**
     * Replace the raw list of ids set by gantt by link and unlink commands
     * so that only the partner/resource selected by the user changes instead of replacing
     * all partners/resources with the new one.
     *
     * @override
     */
    _scheduleToData(schedule) {
        const data = super._scheduleToData(...arguments);

        if (!this.metaData.groupedBy) {
            return data;
        }
        if (this.metaData.groupedBy[0] === "resource_ids") {
            const targetId = data.resource_ids && data.resource_ids[0];
            const commands = [];
            if (schedule.originId) {
                commands.push([3, schedule.originId, 0]);
            }
            if (targetId) {
                commands.push([4, targetId, 0]);
            }
            return {
                ...data,
                resource_ids: commands,
            };
        }
        if (
            this.metaData.groupedBy[0] === "partner_ids" &&
            data.partner_ids?.[0] !== schedule.originId // attendee_ids will be messed up without this check
        ) {
            const commands = [];
            if (schedule.originId) {
                commands.push([3, schedule.originId, 0]);
            }
            if (data.partner_ids?.[0]) {
                commands.push([4, data.partner_ids[0], 0]);
            }
            return {
                ...data,
                partner_ids: commands,
            };
        }
        return data;
    }

    getRangeFromDate(rangeId, date) {
        const startDate = localStartOf(date, rangeId);
        const stopDate = startDate.plus({ [rangeId]: 1 }).minus({ day: 1 });
        return { focusDate: date, startDate, stopDate, rangeId };
    }
}
