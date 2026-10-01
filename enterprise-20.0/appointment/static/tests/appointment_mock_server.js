import { session } from "@web/session";
import { onRpc } from "@web/../tests/web_test_helpers";


onRpc("/appointment/appointment_type/search_create_anytime", function searchCreateAnytime() {
    let anytimeAppointmentID = this.env["appointment.type"].search([
        ["category", "=", "anytime"],
        ["staff_user_ids", "in", [session.user_id[0]]],
    ])[0];
    if (!anytimeAppointmentID) {
        anytimeAppointmentID = this.env["appointment.type"].create({
            name: "Anytime with Actual User",
            staff_user_ids: [session.user_id[0]],
            category: "anytime",
            website_published: true,
        });
    }
    return {
        appointment_type: { id: anytimeAppointmentID },
        invite_url: `http://amazing.odoo.com/appointment/3?filter_staff_user_ids=%5B${session.user_id[0]}%5D`,
    };
});

onRpc(
    "/appointment/appointment_type/get_calendar_slot_editor_info",
    async function getBookUrl(request) {
        const { params } = await request.json();
        const { appointment_type_id } = params;
        const record = this.env["appointment.type"].read(appointment_type_id, [
            "active",
            "appointment_duration",
            "appointment_tz",
            "category",
            "category_slot_scheduling",
            "end_datetime",
            "slot_creation_interval",
            "start_datetime",
            "user_can_manage_slots",
        ])[0];
        return {
            appointment_type: {
                ...record,
                // the mock model has no category_slot_scheduling compute; derive it from category
                category_slot_scheduling:
                    record.category_slot_scheduling ||
                    (record.category === "custom" ? "flexible" : "weekly"),
            },
            invite_url: `http://amazing.odoo.com/appointment/${appointment_type_id}?filter_staff_user_ids=%5B${session.user_id[0]}%5D`,
        };
    }
);
