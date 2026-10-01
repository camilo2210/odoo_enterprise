import { expect } from "@odoo/hoot";
import { range } from "@web/core/utils/numbers";
import { defineModels, fields, onRpc } from "@web/../tests/web_test_helpers";

import { SaleOrderLine, ProductProduct } from "@sale_project/../tests/project_task_model";
import { hrTimesheetModels } from "@hr_timesheet/../tests/hr_timesheet_models";
import { defineTimesheetModels as defineTimesheetGridModels } from "@timesheet_grid/../tests/hr_timesheet_models";
import { projectModels } from "@project/../tests/project_models";

export class ProjectProject extends projectModels.ProjectProject {
    allow_billable = fields.Boolean();
}

export class ProjectTask extends projectModels.ProjectTask {
    active = fields.Boolean({ default: true });
    allow_billable = fields.Boolean();
    rotting_days = fields.Integer();
    duration_tracking = fields.Json();

    _views = {
        list: '<list><field name="name"/></list>',
        form: `
            <form>
                <field name="stage_id" widget="task_rotting_statusbar_duration"/>
                <field name="name"/>
                <field name="active" invisible="1"/>
                <field name="allow_timesheets" invisible="1"/>
                <field name="allow_billable" invisible="1"/>
                <field name="is_template" invisible="1"/>
            </form>`,
    };
}

export class HRTimesheet extends hrTimesheetModels.HRTimesheet {
    billable_type = fields.Selection({
        selection: [
            ["01_revenues_fixed", "Service Revenue (Fixed Price)"],
            ["10_service_revenues", "Service Revenue (Time & Materials)"],
            ["05_revenues_milestones", "Service Revenue (Milestones)"],
            ["07_revenues_manual", "Service Revenue (Manual)"],
            ["19_materials", "Materials"],
            ["11_other_revenues", "Other Revenue"],
            ["02_billable_fixed", "Timesheets (Fixed Price)"],
            ["04_billable_time", "Timesheets (Time & Materials)"],
            ["06_billable_milestones", "Timesheets (Milestones)"],
            ["08_billable_manual", "Timesheets (Manual)"],
            ["09_non_billable", "Timesheets (Non-Billable)"],
            ["12_vendor_bill", "Vendor Bills"],
            ["30_other_costs", "Other Costs"],
        ],
    });
    so_line = fields.Many2one({ relation: "sale.order.line" });
    allow_billable = fields.Boolean({
        relation: "project.project",
        relation_field: "allow_billable",
        default: true,
    });
    is_billable = fields.Boolean();
    has_available_so = fields.Boolean({ default: true });

    _get_aw_timesheet_fields_specification() {
        return {
            ...super._get_aw_timesheet_fields_specification(),
            allow_billable: {},
            is_billable: {},
            has_available_so: {},
            so_line: {
                fields: { display_name: {} },
            },
        };
    }
}
hrTimesheetModels.HRTimesheet = HRTimesheet;

HRTimesheet._records = [
    {
        name: "youpi",
        id: 1,
        project_id: 1,
        employee_id: 2,
        date: "2017-01-24",
        unit_amount: 2.5,
        billable_type: "04_billable_time",
        so_line: false,
    },
    {
        name: "bop",
        id: 2,
        project_id: 1,
        task_id: 1,
        employee_id: 1,
        date: "2017-01-25",
        unit_amount: 25,
        billable_type: "02_billable_fixed",
        so_line: false,
    },
    {
        name: "Sabaton",
        id: 3,
        project_id: 1,
        task_id: 1,
        employee_id: 3,
        date: "2017-01-25",
        unit_amount: 5.5,
        billable_type: "09_non_billable",
        so_line: false,
    },
    {
        name: "chaos",
        id: 4,
        project_id: 2,
        task_id: 3,
        employee_id: 1,
        date: "2017-01-27",
        unit_amount: 10,
        billable_type: "08_billable_manual",
        so_line: false,
    },
    {
        name: "sakamoto",
        id: 5,
        project_id: 2,
        task_id: 2,
        employee_id: 2,
        date: "2017-01-27",
        unit_amount: -3.5,
        billable_type: "09_non_billable",
        so_line: false,
    },
    {
        name: "frieren",
        id: 6,
        project_id: 2,
        task_id: 1,
        employee_id: 4,
        date: "2017-01-26",
        unit_amount: 4,
        billable_type: "09_non_billable",
        so_line: false,
    },
];

HRTimesheet._views.kanban = `
    <kanban js_class="my_timesheets_kpi_leaderboard_kanban">
        <templates>
            <field name="name"/>
            <t t-name="card">
                <field name="employee_id"/>
                <field name="project_id"/>
                <field name="task_id"/>
                <field name="date"/>
                <field name="unit_amount"/>
            </t>
        </templates>
    </kanban>
`;
HRTimesheet._views.list = `
    <list js_class="my_timesheets_kpi_leaderboard_list">
        <field name="name"/>
        <field name="date"/>
        <field name="project_id"/>
        <field name="task_id"/>
        <field name="unit_amount" widget="timesheet_uom"/>
    </list>
`;
HRTimesheet._views.search = HRTimesheet._views.search.replace(
    "<search>",
    `
    <search>
        <filter name="billable" string="Billable" invisible="1" domain="[('billable_type', '!=', '09_non_billable')]"/>
`
);

const kpiData = {
    "2017-01-01": {
        worked_time: 20,
        billable_time: 10,
        billable_time_target: 20,
        billing_rate: 0.5,
        uom: "hours",
    },
    "2017-02-01": {
        worked_time: 40,
        billable_time: 40,
        billable_time_target: 40,
        billing_rate: 1.0,
        uom: "hours",
    },
    "2017-03-01": {
        worked_time: 50,
        billable_time: 0,
        billable_time_target: 150,
        billing_rate: 0,
        uom: "hours",
    },
    "2017-04-01": {
        worked_time: 60,
        billable_time: 30,
        billable_time_target: 60,
        billing_rate: 0.5,
        uom: "hours",
    },
    "2017-05-01": {
        worked_time: 20,
        billable_time: 20,
        billable_time_target: 20,
        billing_rate: 1.0,
        uom: "hours",
    },
    "2019-03-01": {
        worked_time: 20,
        billable_time: 10,
        billable_time_target: 20,
        billing_rate: 0.5,
        uom: "hours",
    },
};

const rankingData = {
    "2017-01-01": {
        leaderboard: range(11).map((id) => ({
            id: id,
            name: `Test ${id}`,
            billable_time_target: 100.0,
            billable_time: 150.0,
            total_time: 150.0,
            billing_rate: 150.0,
        })),
        employee_id: 1,
        tip: "January motivation tip!",
    },
    "2017-02-01": {
        leaderboard: [
            {
                id: 1,
                name: "Administrator",
                billable_time_target: 100.0,
                billable_time: 148.0,
                total_time: 148.0,
                billing_rate: 148.0,
            },
            {
                id: 8,
                name: "User 7",
                billable_time_target: 100.0,
                billable_time: 148.0,
                total_time: 148.0,
                billing_rate: 130.0,
            },
        ],
        employee_id: 1,
        tip: "February productivity tip!",
    },
    "2017-03-01": {
        leaderboard: [
            {
                id: 6,
                name: "User 5",
                billable_time_target: 100.0,
                billable_time: 148.0,
                total_time: 148.0,
                billing_rate: 148.0,
            },
        ],
        employee_id: 1,
        tip: "March productivity tip!",
    },
    "2017-04-01": {
        leaderboard: [
            {
                id: 1,
                name: "Administrator",
                billable_time_target: 100.0,
                billable_time: 20.0,
                total_time: 120.0,
                billing_rate: 5.0,
            },
            {
                id: 2,
                name: "User 1",
                billable_time_target: 50.0,
                billable_time: 40.0,
                total_time: 40.0,
                billing_rate: 80.0,
            },
            {
                id: 3,
                name: "User 2",
                billable_time_target: 100.0,
                billable_time: 60.0,
                total_time: 60.0,
                billing_rate: 60.0,
            },
            {
                id: 4,
                name: "User 3",
                billable_time_target: 200.0,
                billable_time: 80.0,
                total_time: 80.0,
                billing_rate: 40.0,
            },
            {
                id: 5,
                name: "User 4",
                billable_time_target: 500.0,
                billable_time: 100.0,
                total_time: 100.0,
                billing_rate: 20.0,
            },
        ],
        employee_id: 1,
        tip: "Great work this month!",
    },
    "2017-05-01": {
        leaderboard: [
            {
                id: 7,
                name: "User 6",
                billable_time_target: 100.0,
                billable_time: 128.0,
                total_time: 128.0,
                billing_rate: 128.0,
            },
        ],
        employee_id: 1,
        tip: "May excellence tip!",
    },
    "2019-03-01": {
        leaderboard: [
            {
                id: 6,
                name: "User 5",
                billable_time_target: 100.0,
                billable_time: 148.0,
                total_time: 148.0,
                billing_rate: 148.0,
            },
        ],
        employee_id: 1,
        tip: "March productivity tip!",
    },
};
projectModels.ProjectProject = ProjectProject;
projectModels.ProjectTask = ProjectTask;

export function defineTimesheetModels() {
    onRpc(({ method, model, args }) => {
        if (method === "get_kpi_data") {
            expect(model).toBe("account.analytic.line");
            expect.step(method);
            return kpiData[args[0]];
        } else if (method === "get_timesheet_ranking_data") {
            expect(model).toBe("res.company");
            expect.step(method);
            return rankingData[args[0]];
        }
    });
    onRpc("get_timesheet_target_show_rates_value", () => false);
    defineTimesheetGridModels();
    defineModels([SaleOrderLine, ProductProduct]);
}
