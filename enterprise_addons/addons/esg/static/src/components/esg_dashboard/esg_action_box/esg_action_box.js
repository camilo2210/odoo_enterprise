import { Component, t, useProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class EsgActionBox extends Component {
    static template = "esg.ActionBox";
    props = useProps({
        data: t.object(),
    });

    setup() {
        this.actionService = useService("action");
    }

    openActions(item) {
        const additionalContext = {};
        if (item === "reached") {
            additionalContext.search_default_reached_filter = 1;
        } else if (item === "not_reached") {
            additionalContext.search_default_not_reached_filter = 1;
        } else if (item === "undefined") {
            additionalContext.search_default_target_undefined_filter = 1;
        }
        this.actionService.doAction("esg.action_view_esg_action", { additionalContext });
    }

    openActionForm() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "esg.action",
            views: [[false, "form"]],
            target: "current",
        });
    }
}
