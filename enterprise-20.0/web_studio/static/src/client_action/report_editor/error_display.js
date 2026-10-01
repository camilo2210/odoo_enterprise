import { Component, computed, proxy, t, useProps } from "@odoo/owl";
import { router } from "@web/core/browser/router";
import { useService } from "@web/core/utils/hooks";
import { humanReadableError } from "@web_studio/client_action/report_editor/utils";

export class ErrorDisplay extends Component {
    static template = "web_studio.ErrorDisplay";
    props = useProps({
        error: t.object(),
    });

    error = computed(() => humanReadableError(this.props.error));

    setup() {
        this.state = proxy({ showTrace: false });
        this.action = useService("action");
    }
    openRecord(resModel, resId) {
        const action = {
            type: "ir.actions.act_window",
            target: "new",
            res_model: resModel,
            res_id: resId,
            views: [[false, "form"]],
            context: {
                studio: "0",
            },
        };
        this.action.doAction(action);
    }
    urlFor(model, resId, viewType = "form") {
        return router.stateToUrl({ action: "base.action_ui_view", model, resId });
    }
}
