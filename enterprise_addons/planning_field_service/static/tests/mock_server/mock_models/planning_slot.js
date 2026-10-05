import { fields } from "@web/../tests/web_test_helpers";

import { planningModels } from "@planning/../tests/planning_mock_models";

export class PlanningSlot extends planningModels.PlanningSlot {
    partner_id = fields.Many2one({ string: "Partner", relation: "res.partner" });
    travel_time_in = fields.Float();
    travel_time_out = fields.Float();
    travel_times_up_to_date = fields.Boolean({ compute: "_compute_travel_times_up_to_date" });
    can_edit = fields.Boolean({});

    _records = [
        ...planningModels.PlanningSlot._records,
        {
            id: 1,
            name: "Field Service With Current User",
            partner_id: 520,
            resource_ids: [1],
            start_datetime: "2026-01-04 08:00:00",
            end_datetime: "2026-01-04 15:00:00",
            state: "2_published",
            can_edit: true,
        },
        {
            id: 2,
            name: "Field Service Without User",
            partner_id: 1,
            resource_ids: [2],
            start_datetime: "2026-01-04 15:00:00",
            end_datetime: "2026-01-04 16:00:00",
            state: "2_published",
            can_edit: true,
        },
    ];

    _views = {
        ...planningModels.PlanningSlot._views,
        form: `
            <form js_class="planning_form">
                <header>
                    <button name="action_sign_in" string="Start" type="object"/>
                    <button name="action_complete" class="btn-primary" string="Complete" type="object"/>
                </header>
                <sheet>
                    <group>
                        <field name="name"/>
                        <field name="resource_ids" widget="many2many_avatar_resource"/>
                        <field name="partner_id"/>
                        <field name="user_ids" invisible="1"/>
                        <field name="can_edit" invisible="1"/>
                    </group>
                </sheet>
            </form>
        `,
        gantt: `
            <gantt js_class="planning_gantt" date_start="start_datetime" date_stop="end_datetime" total_row="1" default_range="week"
                    precision="{'day': 'hour:quarter', 'week': 'day:full', 'month': 'day:full', 'year': 'day:full'}"
                    buffer_start="travel_time_in" buffer_stop="travel_time_out">
                <field name="allocated_percentage"/>
                <field name="resource_ids"/>
                <field name="name"/>
                <field name="partner_id"/>
                <field name="state" invisible="1"/>
                <field name="user_ids" invisible="1"/>
                <field name="travel_distance_in" invisible="1"/>
                <field name="travel_distance_out" invisible="1"/>
                <field name="travel_times_up_to_date" invisible="1"/>
                <field name="can_edit" invisible="1"/>
            </gantt>
        `,
        calendar: `
            <calendar class="o_planning_calendar_test"
                      event_open_popup="true"
                      date_start="start_datetime"
                      date_stop="end_datetime"
                      mode="month"
                      js_class="planning_calendar"
            >
                <field name="resource_ids"/>
                <field name="role_id"/>
                <field name="partner_id"/>
                <field name="state" invisible="1"/>
                <field name="user_ids" invisible="1"/>
                <field name="can_edit" invisible="1"/>
            </calendar>
        `,
    };

    _compute_travel_times_up_to_date() {
        for (const slot of this) {
            slot.travel_times_up_to_date =
                slot.travel_times_up_to_date ||
                !slot.partner_id ||
                !slot.resource_ids.length ||
                !slot.start_datetime;
        }
    }
}
