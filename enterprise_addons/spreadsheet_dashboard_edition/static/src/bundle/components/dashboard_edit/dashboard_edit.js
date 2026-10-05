import { Component, onWillStart, t, usePlugin, useProps } from "@odoo/owl";
import { user } from "@web/core/user";
import { dashboardActionRegistry } from "@spreadsheet_dashboard/bundle/dashboard_action/dashboard_action";
import { _t } from "@web/core/l10n/translation";
import { DebugModePlugin } from "@web/core/debug_mode_plugin";

export class DashboardEdit extends Component {
    static template = "spreadsheet_dashboard_edition.DashboardEdit";

    props = useProps({
        onClick: t.function(),
        dashboardId: t.number(),
        data: t.object(),
    });

    debugMode = usePlugin(DebugModePlugin);

    setup() {
        this.isDashboardAdmin = false;
        onWillStart(async () => {
            if (this.debugMode.isActive()) {
                this.isDashboardAdmin = await user.hasGroup(
                    "spreadsheet_dashboard.group_dashboard_manager"
                );
            }
        });
    }
    onClick() {
        return this.props.onClick(this.props.dashboardId);
    }

    get tooltip() {
        return this.props.data.is_from_data
            ? _t(
                  "Editing standard dashboards is not recommended. Changes will be lost on Odoo upgrades."
              )
            : _t("Edit");
    }
}

dashboardActionRegistry.add("dashboard_edit", DashboardEdit);
