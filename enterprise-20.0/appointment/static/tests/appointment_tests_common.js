import { CalendarFilters } from "@calendar/../tests/mock_server/mock_models/calendar_filters";
import { mailModels } from "@mail/../tests/mail_test_helpers";
import { defineModels, fields, models } from "@web/../tests/web_test_helpers";

export class CalendarEvent extends models.Model {
    _name = "calendar.event";

    id = fields.Integer({ string: "ID" });
    active = fields.Boolean({ string: "Active" });
    name = fields.Char({ string: "Name" });
    user_id = fields.Many2one({ string: "User", relation: "res.users" });
    partner_id = fields.Many2one({
        string: "Partner",
        relation: "res.partner",
        related: "user_id.partner_id.id",
    });
    start_date = fields.Date({ string: "Start date" });
    stop_date = fields.Date({ string: "Stop date" });
    start = fields.Datetime({ string: "Start datetime" });
    stop = fields.Datetime({ string: "Stop datetime" });
    allday = fields.Boolean({ string: "Allday" });
    partner_ids = fields.Many2many({ string: "Attendees", relation: "res.partner" });
    resource_ids = fields.Many2many({ string: "Resources", relation: "appointment.resource" });
    appointment_status = fields.Selection({
        selection: [
            ['cancelled', 'Cancelled'],
            ['request', 'Request'],
            ['booked', 'Booked'],
            ['attended', 'Checked-In'],
            ['no_show', 'No Show'],
        ],
        string: "Appointment Status",
    });
    appointment_type_id = fields.Many2one({
        string: "Appointment Type",
        relation: "appointment.type",
    });

    _records = [
        {
            id: 1,
            active: true,
            user_id: 100,
            partner_id: 100,
            name: "Event 1",
            start: "2022-01-12 10:00:00",
            stop: "2022-01-12 11:00:00",
            allday: false,
            appointment_status: 'booked',
            partner_ids: [100, 214],
        },
        {
            id: 2,
            active: true,
            user_id: 214,
            partner_id: 214,
            name: "Event 2",
            start: "2022-01-05 10:00:00",
            stop: "2022-01-05 11:00:00",
            allday: false,
            appointment_status: 'booked',
            partner_ids: [214, 216],
        },
        {
            id: 3,
            active: true,
            user_id: 216,
            partner_id: 216,
            name: "Event 3",
            start: "2022-01-05 10:00:00",
            stop: "2022-01-05 11:00:00",
            allday: false,
            appointment_status: 'booked',
            partner_ids: [216, 100, 214, 217],
        },
    ];
    has_access = function () {
        return Promise.resolve(true);
    };
}

export class AppointmentType extends models.ServerModel {
    _name = "appointment.type";

    name = fields.Char();
    appointment_duration = fields.Float({ default: 1 });
    // mirror the real model's `user.tz` default with the current viewer timezone, so slots
    // aren't spuriously converted; timezone-specific tests override it explicitly
    appointment_tz = fields.Char({ default: () => luxon.Settings.defaultZone.name });
    website_url = fields.Char();
    staff_user_ids = fields.Many2many({ relation: "res.users" });
    website_published = fields.Boolean();
    user_can_manage_slots = fields.Boolean({ default: true });
    start_datetime = fields.Datetime();
    end_datetime = fields.Datetime();
    slot_creation_interval = fields.Float({ default: 1 });
    slot_ids = fields.One2many({ relation: "appointment.slot" });
    schedule_based_on = fields.Selection({
        selection: [
            ["users", "Users"],
            ["resources", "Resources"],
        ],
        default: "users",
    });
    category = fields.Selection({
        selection: [
            ["website", "Website"],
            ["custom", "Specific Slots"],
        ],
    });

    _records = [
        {
            id: 1,
            name: "Very Interesting Meeting",
            website_url: "/appointment/1",
            website_published: true,
            schedule_based_on: "users",
            staff_user_ids: [214, 216],
            category: "website",
        },
        {
            id: 2,
            name: "Test Appointment",
            website_url: "/appointment/2",
            website_published: true,
            schedule_based_on: "users",
            staff_user_ids: [100],
            category: "website",
        },
    ];
}

class AppointmentResource extends models.Model {
    _name = "appointment.resource";
}

export class AppointmentSlot extends models.ServerModel {
    _name = "appointment.slot";

    appointment_type_id = fields.Many2one({ relation: "appointment.type" });
    start_datetime = fields.Datetime({ string: "Start" });
    end_datetime = fields.Datetime({ string: "End" });
    duration = fields.Float({ string: "Duration" });
    slot_type = fields.Selection({
        string: "Slot Type",
        selection: [
            ["recurring", "Regular"],
            ["unique", "One Shot"],
        ],
    });
    allday = fields.Boolean();
    weekday = fields.Selection({
        selection: [
            ["1", "Monday"],
            ["2", "Tuesday"],
            ["3", "Wednesday"],
            ["4", "Thursday"],
            ["5", "Friday"],
            ["6", "Saturday"],
            ["7", "Sunday"],
        ],
    });
    start_hour = fields.Float();
    end_hour = fields.Float();
}

export class ResPartner extends mailModels.ResPartner {
    _records = [
        ...mailModels.ResPartner._records,
        {
            id: 100,
            display_name: "Partner 1",
            name: "Partner 1",
            email: "partner1@test.lan",
            phone: "0467121212",
            user_ids: [100],
        },
        {
            id: 214,
            display_name: "Partner 214",
            name: "Partner 214",
            email: "",
            phone: "012123123",
            user_ids: [214],
        },
        {
            id: 216,
            display_name: "Partner 216",
            name: "Partner 216",
            email: "partner216@test.lan",
            phone: "",
            user_ids: [216],
        },
        {
            id: 217,
            display_name: "Contact Partner",
            name: "Contact Partner",
            email: "partner@contact.lan",
            phone: "",
            user_ids: [],
        },
    ];
}

export class ResUsers extends mailModels.ResUsers {
    _records = [
        ...mailModels.ResUsers._records,
        { id: 100, name: "User 1", partner_id: 100 },
        { id: 214, name: "User 214", partner_id: 214 },
        { id: 216, name: "User 216", partner_id: 216 },
    ];
}

export function defineAppointmentModels() {
    return defineModels({
        ...mailModels,
        AppointmentResource,
        AppointmentSlot,
        AppointmentType,
        CalendarEvent,
        CalendarFilters,
        ResPartner,
        ResUsers,
    });
}
