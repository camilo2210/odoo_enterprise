import { _t } from "@web/core/l10n/translation";
import { ProductCatalogKanbanController } from "@product/product_catalog/kanban_controller";

export class FSMProductCatalogKanbanController extends ProductCatalogKanbanController {
    setup() {
        super.setup();
        const { intervention_id } = this.props.context;
        this.interventionId = intervention_id;
    }

    /**
     * @override
     * overriding useless method to prevent wrong orm call
     *
     * **/
    setOrderStateInfo() {}

    _defineButtonContent() {
        if (this.props.context.active_model === "planning.slot") {
            this.buttonString = _t("Back to Shift");
        }
    }

    async backToQuotation() {
        if (this.env.config.breadcrumbs.length > 1) {
            await this.actionService.restore();
        } else {
            await this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: this.orderResModel,
                views: [[false, "form"]],
                view_mode: "form",
                res_id: this.interventionId,
            });
        }
    }
}
