import { EsgGraphDashboard } from "@esg/components/esg_dashboard/esg_graph_dashboard/esg_graph_dashboard";
import { Component, t, useProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class EsgCarbonFootprintBox extends Component {
    static template = "esg.CarbonFootprintBox";
    static components = { EsgGraphDashboard };

    props = useProps({
        data: t.object(),
    });

    setup() {
        this.actionService = useService("action");
    }

    openCarbonAnalyticsViews() {
        this.actionService.doAction("esg.action_carbon_emission_report_analytics_views");
    }

    openCarbonReport() {
        this.actionService.doAction("esg.action_view_carbon_report");
    }
}
