import { ProductCatalogKanbanModel } from "@product/product_catalog/kanban_model";

export class FSMProductCatalogKanbanModel extends ProductCatalogKanbanModel {
    _getOrderLinesInfoParams(params, productIds) {
        return {
            ...super._getOrderLinesInfoParams(params, productIds),
            planning_slot_id: params.context.intervention_id,
            section_id: this.env.searchModel.selectedSectionId,
            order_id: params.context.order_id || false,
            intervention_id: params.context.intervention_id || params.context.active_id,
        };
    }
}
