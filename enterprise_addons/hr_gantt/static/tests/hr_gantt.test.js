import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { queryAll } from "@odoo/hoot-dom";
import { mockDate } from "@odoo/hoot-mock";
import {
    defineModels,
    fields,
    models,
    onRpc,
    toggleMenuItem,
    toggleSearchBarMenu,
} from "@web/../tests/web_test_helpers";
import { mountGanttView } from "@web_gantt/../tests/web_gantt_test_helpers";

describe.current.tags("desktop");

class Employee extends models.Model {
    _name = "hr.employee.public";

    _records = [
        { id: 1, display_name: "Mario" },
        { id: 2, display_name: "Luigi" },
        { id: 3, display_name: "Yoshi" },
    ];
}

class Task extends models.Model {
    start = fields.Datetime();
    stop = fields.Datetime();
    employee_id = fields.Many2one({ relation: "hr.employee.public" });
    foo = fields.Char();

    _records = [
        {
            id: 1,
            display_name: "Task 1",
            start: "2018-11-30 18:30:00",
            stop: "2018-12-31 18:29:59",
            employee_id: 1,
            foo: "Foo 1",
        },
        {
            id: 2,
            display_name: "Task 2",
            start: "2018-12-17 11:30:00",
            stop: "2018-12-22 06:29:59",
            employee_id: 2,
            foo: "Foo 2",
        },
        {
            id: 3,
            display_name: "Task 3",
            start: "2018-12-27 06:30:00",
            stop: "2019-01-03 06:29:59",
            employee_id: 3,
            foo: "Foo 1",
        },
        {
            id: 4,
            display_name: "Task 4",
            start: "2018-12-19 18:30:00",
            stop: "2018-12-20 06:29:59",
            employee_id: 1,
            foo: "Foo 3",
        },
        {
            id: 5,
            display_name: "Task 5",
            start: "2018-12-21 10:30:00", // 11:30:00 CET
            stop: "2018-12-21 11:29:59",  // 12:29:59 CET
            employee_id: 1,
            foo: "Foo 3",
        },
        {
            id: 6,
            display_name: "Task 6",
            start: "2018-12-22 10:30:00", // 11:30:00 CET
            stop: "2018-12-22 11:59:59",  // 12:59:59 CET
            employee_id: 1,
            foo: "Foo 3",
        },
    ];
}

defineMailModels();
defineModels([Employee, Task]);

const arch = `<gantt js_class="hr_gantt" date_start="start" date_stop="stop" />`;

beforeEach(() => {
    mockDate("2018-12-20 07:00:00", +1);
});

test("hr gantt view pill rounding", async () => {
    expect.assertions(7);
    await mountGanttView({ resModel: "task", arch });
    const [task4, task5, task6] = queryAll(".o_gantt_pill_wrapper.o_draggable").reduce(
        (acc, node) => ["task,4", "task,5", "task,6"].includes(node.innerText)
            ? acc.concat(node.getBoundingClientRect())
            : acc,
        [],
    );
    const [col19, col20, col21, col22] = queryAll(".o_gantt_header_cell").reduce(
        (acc, node) => "19" <= node.innerText && node.innerText <= "22"
            ? acc.concat(node.getBoundingClientRect())
            : acc,
        [],
    );
    expect(task4.width).toBe(col19.width, { message: "Task 4 should take up 2 half-days" });
    expect(task5.width).toBe(col21.width / 2, { message: "Task 5 should take up 1 half-day" });
    expect(task6.width).toBe(col22.width / 2, { message: "Task 6 should take up 1 half-day" });
    expect(task4.left).toBeWithin(col19.x, col20.x, { message: "Task 4 should start the 19th" });
    expect(task4.right).toBeWithin(col20.x, col21.x, { message: "Task 4 should end the 20th" });
    expect(task5.left).toBe(col21.left, { message: "Task 5 should display before noon" });
    expect(task6.right).toBe(col22.right, { message: "Task 6 should display after noon" });
});

/*
 * The `user_domain` passed in context to `get_gantt_data` should only
 * reflect what the user explicitly typed/applied via the search bar.
 * `domain` should contain all the filters/domains, including `user_domain`
 */
test("user_domain contains domain from search bar, domain contains all filters", async () => {
    onRpc("get_gantt_data", (args) => {
        expect.step({
            domain: args.kwargs.domain,
            user_domain: args.kwargs.context.user_domain,
        });
    });

    await mountGanttView({
        resModel: "task",
        arch: `<gantt js_class="hr_gantt" date_start="start" default_group_by='employee_id' date_stop="stop"/>`,
        // domain implicitly applied. it should not appear in user_domain
        domain: [["employee_id.name", "=", "Princess Cadence"]],
        // available filters that can be clicked by user
        searchViewArch: `
            <search>
                <filter name="filter_pony" string="Is Pony" domain="[['kind', '=', 'pony']]"/>
            </search>
        `,
    });

    expect.verifySteps(
        [
            {
                domain: [
                    "&",
                        ["employee_id.name", "=", "Princess Cadence"],
                    "&",
                        ["start", "<", "2019-02-28 23:00:00"],
                        ["stop", ">", "2018-11-30 23:00:00"],
                ],
                user_domain: [],
            },
        ],
        { message: "`domain` should contain all gantt filters, but no filters are defined in the search bar so `user_domain` should be empty" }
    );

    // make as if the user clicked on the "Pony" filter
    await toggleSearchBarMenu();
    await toggleMenuItem("Is Pony");

    expect.verifySteps(
        [
            {
                domain: [
                    "&",
                        "&",
                            ["employee_id.name", "=", "Princess Cadence"],
                            ["kind", "=", "pony"],
                    "&",
                        ["start", "<", "2019-02-28 23:00:00"],
                        ["stop", ">", "2018-11-30 23:00:00"],
                ],
                user_domain: [["kind", "=", "pony"]],
            },
        ],
        { message: "`domain` should contain all gantt filters (including `user_domain`), `user_domain` should contain the filters defined in the search bar only" }
    );
});
