import { fields, getKwArgs, models, onRpc } from "@web/../tests/web_test_helpers";

import { projectModels } from "@project/../tests/project_models";
import {
    defineTimesheetModels as defineHRTimesheetModels,
    hrTimesheetModels,
} from "@hr_timesheet/../tests/hr_timesheet_models";
import { timerModels } from "@timer/../tests/timer_models";

export class ProjectProject extends projectModels.ProjectProject {
    allow_timesheets = fields.Boolean();

    _records = [
        { id: 1, name: "P1", allow_timesheets: true },
        { id: 2, name: "Webocalypse Now", allow_timesheets: true },
    ];
}

export class ProjectTask extends projectModels.ProjectTask {
    allow_timesheets = fields.Boolean();

    get_additional_groups(domain, specification, limit) {
        const kwargs = getKwArgs(arguments, "domain", "specification", "limit");
        ({ domain, specification, limit } = kwargs);
        return this.web_search_read(domain, specification, { limit });
    }

    _records = [
        { id: 1, name: "BS task", project_id: 1 },
        { id: 2, name: "Another BS task", project_id: 2 },
        { id: 3, name: "yet another task", project_id: 2 },
    ];
}

export class HREmployeePublic extends models.Model {
    _name = "hr.employee.public";

    name = fields.Char();

    _records = [
        { id: 1, name: "Mario" },
        { id: 2, name: "Luigi" },
        { id: 3, name: "Yoshi" },
        { id: 4, name: "Toad" },
    ];
}

export class HRTimesheet extends hrTimesheetModels.HRTimesheet {
    user_id = fields.Many2one({ relation: "res.users" });
    company_id = fields.Many2one({ relation: "res.company" });
    employee_id = fields.Many2one({ relation: "hr.employee.public" });
    date = fields.Date({ default: "2019-03-11" });
    task_id = fields.Many2one({
        relation: "project.task",
        onChange(record) {
            const task =
                record.task_id && this.env["project.task"].find((t) => t.id === record.task_id);
            if (task?.project_id) {
                record.project_id = task.project_id;
            }
        },
    });
    selection_field = fields.Selection({
        selection: [
            ["abc", "ABC"],
            ["def", "DEF"],
            ["ghi", "GHI"],
        ],
    });

    grid_unavailability(dateStart, dateEnd) {
        const { res_ids: employeeIds } = arguments[2];
        const unavailabilityDates = Object.fromEntries(
            employeeIds.map((employee) => [employee, [dateStart, dateEnd]])
        );
        unavailabilityDates.false = [dateStart, dateEnd];
        return unavailabilityDates;
    }

    get_assistant_data() {
        return {
            rounding_values: {
                minimum: 15,
                rounding: 15,
            },
            odoo_models_data: [
                {
                    model: "project.task",
                    label: "Working on Task in Project App",
                    url_regex: `${window.location.origin}/odoo/(?:[^/?#]+/)*(?:to\\-do|tasks|project_sharing|my\\-tasks|all\\-tasks|project\\.task)/(\\d+)(?:\\?|$)`,
                },
                {
                    model: "project.project",
                    label: "Working on Project in Project App",
                    url_regex: `${window.location.origin}/odoo/(?:[^/?#]+/)*(?:project\\-configuration|project|project\\.project)/(\\d+)(?:\\?|$)`,
                },
            ],
        };
    }

    get_assistant_events(date) {
        return [];
    }

    get_aw_app_from_urls(urls) {
        return {};
    }

    resolve_gmail_partners(emails) {
        return {};
    }

    resolve_assistant_models_targets(ids_per_model) {
        return {};
    }

    _get_aw_timesheet_fields_specification() {
        return {
            id: {},
            name: {},
            date: {},
            user_id: {
                fields: {
                    display_name: {},
                },
            },
            project_id: {
                fields: {
                    display_name: {},
                },
            },
            task_id: {
                fields: {
                    display_name: {},
                },
            },
            unit_amount: {},
            company_id: {
                fields: {
                    display_name: {},
                },
            },
        };
    }

    get_aw_timesheet_data(date) {
        const specification = this._get_aw_timesheet_fields_specification();
        const domain = [
            ["date", "=", date],
            ["user_id", "=", this.env.user.id],
        ];
        const timesheets = this.web_search_read(domain, specification);
        return {
            working_hours: 7.6,
            specification: specification,
            timesheets: timesheets,
        };
    }

    _records = [
        {
            name: "youpi",
            id: 1,
            project_id: 1,
            employee_id: 2,
            date: "2017-01-24",
            unit_amount: 2.5,
        },
        {
            name: "bop",
            id: 2,
            project_id: 1,
            task_id: 1,
            employee_id: 1,
            date: "2017-01-25",
            unit_amount: 25,
        },
        {
            name: "Sabaton",
            id: 3,
            project_id: 1,
            task_id: 1,
            employee_id: 3,
            date: "2017-01-25",
            unit_amount: 5.5,
        },
        {
            name: "chaos",
            id: 4,
            project_id: 2,
            task_id: 3,
            employee_id: 1,
            date: "2017-01-27",
            unit_amount: 10,
        },
        {
            name: "sakamoto",
            id: 5,
            project_id: 2,
            task_id: 2,
            employee_id: 2,
            date: "2017-01-27",
            unit_amount: -3.5,
        },
        {
            name: "frieren",
            id: 6,
            project_id: 2,
            task_id: 1,
            employee_id: 4,
            date: "2017-01-26",
            unit_amount: 4,
        },
    ];

    _views = {
        form: `
            <form string="Add a line">
                <group>
                    <group>
                        <field name="project_id"/>
                        <field name="task_id"/>
                        <field name="date"/>
                        <field name="unit_amount" string="Time spent"/>
                    </group>
                </group>
            </form>
        `,
        grid: `
            <grid js_class="timesheet_grid" barchart_total="1" create_inline="1">
                <field name="employee_id" type="row" widget="timesheet_many2one_avatar_employee"/>
                <field name="project_id" type="row" widget="timesheet_many2one"/>
                <field name="task_id" type="row" widget="timesheet_many2one"/>
                <field name="date" type="col">
                    <range name="week" string="Week" span="week" step="day"/>
                    <range name="month" string="Month" span="month" step="day"/>
                    <range name="year" string="Year" span="year" step="month"/>
                </field>
                <field name="unit_amount" type="measure" widget="float_time"/>
                <button string="Action" type="action" name="action_name" />
            </grid>
        `,
        "grid,1": `
            <grid js_class="timesheet_grid" barchart_total="1" create_inline="1">
                <field name="employee_id" type="row" section="1" widget="timesheet_many2one_avatar_employee"/>
                <field name="project_id" type="row" widget="timesheet_many2one"/>
                <field name="task_id" type="row" widget="timesheet_many2one"/>
                <field name="date" type="col">
                    <range name="week" string="Week" span="week" step="day"/>
                    <range name="month" string="Month" span="month" step="day"/>
                    <range name="year" string="Year" span="year" step="month"/>
                </field>
                <field name="unit_amount" type="measure" widget="float_time"/>
            </grid>
        `,
        search: `
            <search>
                <field name="project_id"/>
                <filter string="Nothing" name="nothing" domain="[(0, '=', 1)]"/>
                <filter string="Project" name="groupby_project" domain="[]" context="{'group_by': 'project_id'}"/>
                <filter string="Task" name="groupby_task" domain="[]" context="{'group_by': 'task_id'}"/>
                <filter string="Selection" name="groupby_selection" domain="[]" context="{'group_by': 'selection_field'}"/>
            </search>
        `,
    };
}

export class AwRule extends models.Model {
    _name = "aw.rule";

    name = fields.Char();
    regex = fields.Char();
    type = fields.Selection({
        selection: [
            ["call", "Call"],
            ["messaging", "Messaging"],
            ["meeting", "Meeting"],
            ["document", "Document"],
            ["spreadsheet", "Spreadsheet"],
            ["presentation", "Presentation"],
            ["development", "Development"],
            ["odoo", "Odoo"],
            ["planning", "Planning"],
            ["other", "Other"],
        ],
        required: true,
    });
    applies_to = fields.Selection({
        selection: [
            ["everyone", "Everyone"],
            ["departments", "Departments"],
            ["private", "Private"],
        ],
        default: "everyone",
    });
    threshold = fields.Float({ default: 1 });
    template = fields.Char();
    description = fields.Char();
    sequence = fields.Integer({ default: 10 });
    project_id = fields.Many2one({ relation: "project.project" });
    task_id = fields.Many2one({ relation: "project.task" });
    always_active = fields.Boolean();
    side_activity = fields.Boolean();

    get_applicable_rules(fields) {
        return this.search_read([], fields);
    }

    _records = [
        {
            id: 1,
            name: "Dev Activity",
            type: "development",
            regex: "https://test.com/(.)",
            template: "Activity $1",
            project_id: 1,
            threshold: 5,
            side_activity: false,
        },
        {
            id: 2,
            name: "Meeting Activity",
            type: "meeting",
            regex: "Activity B",
            template: "Activity B",
            project_id: 2,
            side_activity: true,
            sequence: 2,
        },
        {
            id: 3,
            name: "Github",
            sequence: 10,
            regex: String.raw`\[(FIX|REF|ADD|REM|REV|MOV|REL|IMP|MERGE|CLA|I18N|PERF|CLN|LINT)]\s?(?:\[(?<task_id>\d+)]\s?)(.*?) (?:by .*?) · Pull Request #\d+ · (.*)\|https:\/\/github\.com`,
            type: "development",
            template: "Working on $4",
            description: "[$1] $3",
            project_id: false,
            task_id: false,
            always_active: false,
        },
        {
            id: 4,
            name: "Github",
            sequence: 10,
            regex: String.raw`(?:\[(?<task_id>\d+)]\s?)?(?:\[(FIX|REF|ADD|REM|REV|MOV|REL|IMP|MERGE|CLA|I18N|PERF|CLN|LINT)]\s?)?(.*?) (?:by .*?) · Pull Request #\d+ · (.*)\|https:\/\/github\.com`,
            type: "development",
            template: "Working on $4",
            description: "[$2] $3",
            project_id: false,
            task_id: false,
            always_active: false,
        },
    ];
}

projectModels.ProjectProject = ProjectProject;
projectModels.ProjectTask = ProjectTask;
hrTimesheetModels.HRTimesheet = HRTimesheet;
hrTimesheetModels.HREmployeePublic = HREmployeePublic;
hrTimesheetModels.AwRule = AwRule;
hrTimesheetModels.TimerTimer = timerModels.TimerTimer;

export function defineTimesheetModels() {
    onRpc(({ method, model, args }) => {
        if (
            method === "get_planned_and_worked_hours" &&
            ["project.project", "project.task"].includes(model)
        ) {
            const result = {};
            for (const id of args) {
                result[id] = {
                    allocated_hours: 8,
                    uom: "hours",
                    worked_hours: 7,
                };
            }
            return result;
        } else if (method === "get_daily_working_hours") {
            return {
                1: {
                    "2017-01-25": 6,
                    "2017-01-27": 6,
                },
                2: {
                    "2017-01-24": 8,
                    "2017-01-25": 8,
                },
                3: {
                    "2017-01-24": 0,
                    "2017-01-25": 5.5,
                },
                4: {
                    "2017-01-24": 0,
                    "2017-01-25": 0,
                },
            };
        } else if (method === "get_timesheet_and_working_hours_for_employees") {
            const [employeeIds] = args;
            const result = {};
            for (const employeeId of employeeIds) {
                if (employeeId === 1) {
                    // Employee 11 hasn't done all his hours
                    result[employeeId] = {
                        units_to_work: 987,
                        uom: "hours",
                        worked_hours: 789,
                    };
                } else if (employeeId === 2) {
                    // Employee 7 has done all his hours
                    result[employeeId] = {
                        units_to_work: 654,
                        uom: "hours",
                        worked_hours: 654,
                    };
                } else if (employeeId === 4) {
                    result[employeeId] = {
                        units_to_work: 21,
                        uom: "days",
                        worked_hours: 20,
                    };
                } else {
                    // The others have done too much hours (overtime)
                    result[employeeId] = {
                        units_to_work: 6,
                        uom: "hours",
                        worked_hours: 10,
                    };
                }
            }
            return result;
        } else if (method === "get_last_validated_timesheet_date") {
            return {
                1: false,
                2: "2017-01-30",
                3: "2017-01-29",
            };
        }
    });
    defineHRTimesheetModels();
}
