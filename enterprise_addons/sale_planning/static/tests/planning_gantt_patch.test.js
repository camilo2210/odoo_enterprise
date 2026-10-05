import { click } from "@mail/../tests/mail_test_helpers";
import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { animationFrame, mockDate, mockTimeZone, runAllTimers } from "@odoo/hoot-mock";
import { queryAll, queryAllTexts, waitFor } from "@odoo/hoot-dom";
import {
    contains,
    defineModels,
    fields,
    models,
    mountWithCleanup,
    onRpc,
    patchWithCleanup,
    selectFieldDropdownItem,
} from "@web/../tests/web_test_helpers";
import {
    clickCell,
    editPill,
    hoverGridCell,
    getGridContent,
    mountGanttView,
    SELECTORS,
    selectRange,
} from "@web_gantt/../tests/web_gantt_test_helpers";

import { Component, onWillStart, xml, proxy } from "@odoo/owl";
import { PlanningGanttRenderer } from "@planning/views/planning_gantt/planning_gantt_renderer";
import { Domain } from "@web/core/domain";
import { useService } from "@web/core/utils/hooks";
import { View } from "@web/views/view";
import { SelectCreateDialog } from "@web/views/view_dialogs/select_create_dialog";
import { definePlanningModels, planningModels } from "@planning/../tests/planning_mock_models";

describe.current.tags("desktop");

class PlanningSlot extends planningModels.PlanningSlot {
    _records = [
        {
            id: 1,
            name: "Shift 1",
            role_id: 1,
            sale_line_id: 1,
            resource_ids: false,
            start_datetime: "2021-10-12 08:00:00",
            end_datetime: "2021-10-12 12:00:00",
            allocated_percentage: 0.5,
        },
    ];
}

class PlanningRole extends planningModels.PlanningRole {
    _records = [
        { id: 1, name: "Developer", color: 1 },
        { id: 2, name: "Support Tech", color: 2 },
    ];
}

class Resource extends planningModels.ResourceResource {
    _records = [
        { id: 1, name: "Chaganlal", role_ids: [1], resource_type: "user" },
        { id: 2, name: "Jarvo", role_ids: [2], resource_type: "user" },
    ];
}

class SaleOrderLine extends models.Model {
    _name = "sale.order.line";

    name = fields.Char();

    _records = [{ id: 1, name: "Computer Configuration" }];
}

planningModels.PlanningSlot = PlanningSlot;
planningModels.PlanningRole = PlanningRole;
planningModels.ResourceResource = Resource;

definePlanningModels();
defineModels([SaleOrderLine]);

beforeEach(() => {
    mockDate("2021-10-10 07:00:00", +1);
    onRpc("has_group", () => false);
});

test("Process domain for plan dialog", async function () {
    let renderer;
    patchWithCleanup(PlanningGanttRenderer.prototype, {
        setup() {
            super.setup(...arguments);
            renderer = this;
        },
    });

    class Parent extends Component {
        static template = xml`<View t-props="this.state"/>`;
        static components = { View };
        setup() {
            this.state = proxy({
                arch: `<gantt js_class="planning_gantt" date_start="start_datetime" date_stop="end_datetime" default_scale="week"/>`,
                resModel: "planning.slot",
                type: "gantt",
                domain: [
                    ["start_datetime", "!=", false],
                    ["end_datetime", "!=", false],
                ],
            });
            this.field = useService("field");
            onWillStart(async () => {
                this.state.fields = await this.field.loadFields("planning.slot");
            });
        }
    }

    const parent = await mountWithCleanup(Parent);
    await animationFrame();

    let expectedDomain = Domain.and([
        Domain.and([
            new Domain(["&", ...Domain.TRUE.toList({}), ...Domain.TRUE.toList({})]),
            ["|", ["start_datetime", "=", false], ["end_datetime", "=", false]],
        ]),
        Domain.not([["sale_line_id.state", "=", "cancel"]]),
    ]);
    expect(renderer.getPlanDialogDomain()).toEqual(expectedDomain.toList());

    parent.state.domain = [
        "|",
        ["role_id", "=", false],
        "&",
        ["resource_ids", "!=", false],
        ["start_datetime", "=", false],
    ];
    await animationFrame();

    expectedDomain = Domain.and([
        Domain.and([
            new Domain([
                "|",
                ["role_id", "=", false],
                "&",
                ["resource_ids", "!=", false],
                ...Domain.TRUE.toList({}),
            ]),
            ["|", ["start_datetime", "=", false], ["end_datetime", "=", false]],
        ]),
        Domain.not([["sale_line_id.state", "=", "cancel"]]),
    ]);
    expect(renderer.getPlanDialogDomain()).toEqual(expectedDomain.toList());

    parent.state.domain = ["|", ["start_datetime", "=", false], ["end_datetime", "=", false]];
    await animationFrame();

    expectedDomain = Domain.and([
        Domain.and([
            Domain.TRUE,
            ["|", ["start_datetime", "=", false], ["end_datetime", "=", false]],
        ]),
        Domain.not([["sale_line_id.state", "=", "cancel"]]),
    ]);
    expect(renderer.getPlanDialogDomain()).toEqual(expectedDomain.toList());
});

test("check default planned dates on the plan dialog", async function () {
    expect.assertions(4);
    mockTimeZone(0);
    patchWithCleanup(SelectCreateDialog.prototype, {
        setup() {
            super.setup(...arguments);
            expect(this.props.context.default_start_datetime).toMatch(/^2021-10-11/);
            expect(this.props.context.default_end_datetime).toMatch(/^2021-10-12/);
            expect(this.props.context.focus_date).toMatch(/^2021-10-13/);
            expect(this.props.context.scale).toBe("week");
        },
    });

    PlanningSlot._records.push({
        id: 2,
        role_id: 1,
        sale_line_id: 1,
        resource_ids: false,
        start_datetime: false,
        end_datetime: false,
    });

    await mountGanttView({
        resModel: "planning.slot",
        arch: `<gantt js_class="planning_gantt" date_start="start_datetime" date_stop="end_datetime" default_scale="week"/>`,
    });
    await clickCell("Monday 11", "Week 41, Oct 10 - Oct 16");
});

test("Show shift form dialog only when shifts to plan", async function () {
    onRpc("assign_slot", function ({ model, args }) {
        expect.step("assign_slot");
        this.env[model].write(args[0], args[1]);
        return {
            slots_assigned_ids: args[0],
            schedule_type: "full",
            undo_data: {
                slots_created_ids: [],
                undo_vals: {},
            },
        };
    });

    // Additionally to 'Shift 1', we create a new unplanned shift 'Shift 2' which has a sale_line_id, no start_datetime and no end_datetime values
    PlanningSlot._records.push({
        id: 2,
        name: "Shift 2",
        role_id: 1,
        sale_line_id: 1,
    });
    PlanningSlot._views = {
        form: `<form js_class="planning_form"><field name="name"/></form>`,
        list: `<list><field name="name"/></list>`,
    };

    await mountGanttView({
        resModel: "planning.slot",
        arch: `<gantt js_class="planning_gantt" date_start="start_datetime" date_stop="end_datetime" default_scale="week"/>`,
    });
    await hoverGridCell("Wednesday 13", "Week 41, Oct 10 - Oct 16");
    await clickCell("Wednesday 13", "Week 41, Oct 10 - Oct 16");

    expect(".o_dialog").toHaveCount(1);
    expect(".modal-title").toHaveText("Plan");
    expect(".o_data_cell").toHaveText("Shift 2");

    await click(".o_data_cell");
    await animationFrame();

    const { rows } = getGridContent();
    expect(rows).toEqual([
        {
            pills: [
                {
                    colSpan:
                        "Tuesday 12 Week 41, Oct 10 - Oct 16 -> Tuesday 12 Week 41, Oct 10 - Oct 16",
                    level: 0,
                    title: "Shift 1",
                },
                {
                    colSpan:
                        "Wednesday 13 Week 41, Oct 10 - Oct 16 -> Wednesday 13 Week 41, Oct 10 - Oct 16",
                    level: 0,
                    title: "Shift 2",
                },
            ],
        },
    ]);
    await hoverGridCell("Wednesday 13", "Week 41, Oct 10 - Oct 16");
    await clickCell("Wednesday 13", "Week 41, Oct 10 - Oct 16");
    expect(".o_dialog").toHaveCount(1);
    expect(".modal-title").toHaveText("Add Shift");
    expect.verifySteps(["assign_slot"]);
});

test("Open a dialog to schedule a plan using Open Shift", async function () {
    PlanningSlot._records.push({
        id: 2,
        sale_line_id: 1,
    });
    PlanningSlot._views = {
        list: `<list><field name="sale_line_id"/></list>`,
        form: `
            <form>
                <field name="resource_ids" widget="many2many_avatar_resource"/>
                <field name="start_datetime"/>
                <field name="end_datetime"/>
                <field name="name"/>
            </form>
        `,
    };

    await mountGanttView({
        resModel: "planning.slot",
        arch: '<gantt js_class="planning_gantt" date_start="start_datetime" date_stop="end_datetime" default_scale="week"/>',
        groupBy: ["resource_ids"],
    });
    await hoverGridCell("Wednesday 13", "Week 41, Oct 10 - Oct 16");
    await clickCell("Wednesday 13", "Week 41, Oct 10 - Oct 16");
    await click(".modal-footer .o_create_button");

    await selectFieldDropdownItem("resource_ids", "Jarvo");
    await contains(`[name='name'] input`).edit("Shift-2");
    await contains(`[name='start_datetime'] button`).click();
    await contains(`[name='start_datetime'] input`).edit("2021-10-12 09:00:00");
    await contains(`[name='end_datetime'] button`).click();
    await contains(`[name='end_datetime'] input`).edit("2021-10-12 12:00:00");

    await click(".o_form_button_save");
    await animationFrame();

    const shift2Pill = queryAll(SELECTORS.pill)[1];
    await contains(shift2Pill).click();
    await runAllTimers();
    await waitFor(".o_popover");
    expect(`.o_popover .o_popover_header`).toHaveText("Shift-2");
    expect(queryAllTexts`.o_popover .o_popover_body div`).toEqual([
        "Start: Oct 12, 9:00 AM",
        "Stop: Oct 12, 12:00 PM",
    ]);

    await editPill("Shift-2");
    expect(".o_field_widget[name=resource_ids] .o_tag_badge_text").toHaveText("Jarvo");
});

test("auto plan on gantt view: default end_datetime should cover full range including last day", async function () {
    mockTimeZone(0);
    mockDate("2026-08-17 10:00:00");

    const ranges = [
        ["Day", "2026-08-17 23:59:59"],
        ["Week", "2026-08-22 23:59:59"],
        ["Month", "2026-08-31 23:59:59"],
        ["Quarter", "2026-09-30 23:59:59"],
        ["Year", "2026-12-31 23:59:59"],
    ];

    PlanningSlot._records.push({
        id: 2,
        name: "Slot to plan",
        sale_line_id: 1,
        resource_ids: false,
    });

    let currentExpectedDate = null;
    onRpc("auto_plan_ids", function (params) {
        expect(params.kwargs.context.default_end_datetime).toBe(currentExpectedDate);
        return { open_shift_assigned: [2] };
    });

    await mountGanttView({
        resModel: "planning.slot",
        arch: `
            <gantt
                js_class="planning_gantt"
                date_start="start_datetime"
                date_stop="end_datetime"
                default_group_by="sale_line_id"
            />
        `,
    });

    for (const [label, date] of ranges) {
        currentExpectedDate = date;

        await selectRange(label);

        await click(".o_control_panel_main_buttons button > i[data-icon='arrow_drop_down']");
        await animationFrame();

        await click(".o_gantt_button_auto_plan");
        await animationFrame();
    }
});
