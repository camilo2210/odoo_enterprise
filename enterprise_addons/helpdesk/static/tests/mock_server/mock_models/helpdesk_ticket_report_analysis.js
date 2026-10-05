import { fields, models } from "@web/../tests/web_test_helpers";

export class HelpdeskTicketReportAnalysis extends models.Model {
    _name = "helpdesk.ticket.report.analysis";
    team_id = fields.Many2one({ relation: "helpdesk.team" });
    ticket_id = fields.Many2one({ relation: "helpdesk.ticket" });
    rating_last_value = fields.Integer({ string: "Rating (1-5)" });
    create_date = fields.Datetime();
    close_date = fields.Datetime();

    _records = [
        {
            id: 4,
            team_id: 1,
            create_date: "2024-12-04 00:00:00",
            close_date: "2024-12-15 00:00:00",
        },
        {
            id: 6,
            team_id: 1,
            create_date: "2024-12-04 00:00:00",
            close_date: "2024-12-16 00:00:00",
        },
        {
            id: 9,
            team_id: 2,
            create_date: "2024-12-04 00:00:00",
            close_date: "2024-22-16 00:00:00",
        },
    ];
    _views = {
        graph: /* xml */ `
            <graph string="Tickets Analysis" sample="1" js_class="helpdesk_ticket_analysis_graph">
                <field name="team_id"/>
            </graph>
        `,
        pivot: /* xml */ `
            <pivot string="Tickets Analysis" display_quantity="1" sample="1" js_class="helpdesk_ticket_analysis_pivot">
                <field name="team_id"/>
            </pivot>
        `,
        cohort: /* xml */ `
            <cohort
                string="Tickets Analysis"
                date_start="create_date" date_stop="close_date" interval="week"
                sample="1" js_class="helpdesk_ticket_analysis_cohort"
            />
        `,
    };
}
