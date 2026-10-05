import { fields, defineModels } from "@web/../tests/web_test_helpers";
import { hrTimesheetModels } from "@hr_timesheet/../tests/hr_timesheet_models";
import { defineTimesheetModels } from "@timesheet_grid/../tests/hr_timesheet_models";
import { helpdeskModels } from "@helpdesk/../tests/helpdesk_test_helpers";
import { projectModels } from "@project/../tests/project_models";
import { HrEmployee } from "@hr/../tests/mock_server/mock_models/hr_employee";

export class HelpdeskTeam extends helpdeskModels.HelpdeskTeam {
    _name = "helpdesk.team";

    project_id = fields.Many2one({
        relation: "project.project",
    });
}

export class HelpdeskTicket extends helpdeskModels.HelpdeskTicket {
    _name = "helpdesk.ticket";

    project_id = fields.Many2one({
        relation: "project.project",
    });
}

function getHasHelpdeskTeam(env, projectId) {
    const project = projectId && env["project.project"].find((p) => p.id === projectId);
    return !!project?.has_helpdesk_team;
}

export class HRTimesheet extends hrTimesheetModels.HRTimesheet {
    _name = "account.analytic.line";

    project_id = fields.Many2one({
        relation: "project.project",
        onChange(record) {
            record.has_helpdesk_team = getHasHelpdeskTeam(this.env, record.project_id);
        },
    });

    task_id = fields.Many2one({
        relation: "project.task",
        onChange(record) {
            const task =
                record.task_id && this.env["project.task"].find((t) => t.id === record.task_id);
            if (task?.project_id) {
                record.project_id = task.project_id;
                record.has_helpdesk_team = getHasHelpdeskTeam(this.env, task.project_id);
            }
        },
    });

    helpdesk_ticket_id = fields.Many2one({
        relation: "helpdesk.ticket",
        onChange(record) {
            const ticket =
                record.helpdesk_ticket_id &&
                this.env["helpdesk.ticket"].find((t) => t.id === record.helpdesk_ticket_id);
            if (ticket?.project_id) {
                record.project_id = ticket.project_id;
                record.has_helpdesk_team = getHasHelpdeskTeam(this.env, ticket.project_id);
            }
            record.task_id = false;
        },
    });
    has_helpdesk_team = fields.Boolean({ related: "project_id.has_helpdesk_team" });

    _get_aw_timesheet_fields_specification() {
        return {
            ...super._get_aw_timesheet_fields_specification(),
            has_helpdesk_team: {},
            helpdesk_ticket_id: {
                fields: {
                    display_name: {},
                },
            },
        };
    }
}

export class ProjectProject extends projectModels.ProjectProject {
    _name = "project.project";

    has_helpdesk_team = fields.Boolean();
}

export class HelpdeskTicketReportAnalysis extends helpdeskModels.HelpdeskTicketReportAnalysis {
    employee_id = fields.Many2one({ relation: "hr.employee" });
}

hrTimesheetModels.HRTimesheet = HRTimesheet;
projectModels.ProjectProject = ProjectProject;
helpdeskModels.HelpdeskTicket = HelpdeskTicket;
helpdeskModels.HelpdeskTeam = HelpdeskTeam;
helpdeskModels.HelpdeskTicketReportAnalysis = HelpdeskTicketReportAnalysis;
helpdeskModels.HelpdeskTicket._views = {
    "list": `<list><field name="name"/></list>`,
};

export function defineHelpdeskTimesheetModels() {
    defineModels({
        ...helpdeskModels,
        HrEmployee,
    });
    defineTimesheetModels();
}
