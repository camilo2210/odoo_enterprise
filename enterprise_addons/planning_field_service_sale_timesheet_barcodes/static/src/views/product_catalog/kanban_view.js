import { patch } from "@web/core/utils/patch";
import { fsmProductCatalogKanbanView } from "@planning_field_service_sale_timesheet/views/product_catalog/kanban_view";

patch(fsmProductCatalogKanbanView, {
    buttonTemplate:
        "planning_field_service_sale_timesheet_barcodes.FSMProductCatalogKanbanController.Buttons",
});
