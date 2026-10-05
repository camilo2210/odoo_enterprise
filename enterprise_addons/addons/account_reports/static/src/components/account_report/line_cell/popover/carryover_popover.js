import { ORM } from "@web/core/orm_plugin";
import { ActionPlugin } from "@web/webclient/actions/action_plugin";

import { Component, t, usePlugin, useProps } from "@odoo/owl";

export class AccountReportCarryoverPopover extends Component {
    static template = "account_reports.AccountReportCarryoverPopover";

    props = useProps({
        close: t.function(),
        carryoverData: t.object(),
        options: t.object(),
        context: t.object(),
    });

    actionPlugin = usePlugin(ActionPlugin);
    orm = usePlugin(ORM);

    //------------------------------------------------------------------------------------------------------------------
    //
    //------------------------------------------------------------------------------------------------------------------
    async viewCarryoverLinesAction(expressionId, columnGroupKey) {
        const viewCarryoverLinesAction = await this.orm.call(
            "account.report.expression",
            "action_view_carryover_lines",
            [
                expressionId,
                this.props.options,
                columnGroupKey,
            ],
            {
                context: this.props.context,
            }
        );
        this.props.close();
        return this.actionPlugin.doAction(viewCarryoverLinesAction);
    }
}
