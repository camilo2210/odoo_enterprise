import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListRenderer } from "@web/views/list/list_renderer";
import { ActionHelper } from "@web/views/action_helper";

export class CommissionPlanActionHelper extends ActionHelper {
    static template = "sale_commission.PlanActionHelper";
}

export class CommissionPlanListRenderer extends ListRenderer {
    static components = {
        ...ListRenderer.components,
        ActionHelper: CommissionPlanActionHelper,
    };
}

registry.category("views").add("commission_plan_list", {
    ...listView,
    Renderer: CommissionPlanListRenderer,
});
