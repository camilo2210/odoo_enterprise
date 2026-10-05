import { registry } from "@web/core/registry";
import { saleFileUploadKanbanView } from "@sale/views/sale_file_upload_kanban/sale_file_upload_kanban_view";
import { SaleFileUploadKanbanRenderer } from "@sale/views/sale_file_upload_kanban/sale_file_upload_kanban_renderer";
import { Dashboard } from "@sale_renting/js/dashboard/dashboard";

export class RentalFileUploadKanbanRenderer extends SaleFileUploadKanbanRenderer {
    static components = {
        ...SaleFileUploadKanbanRenderer.components,
        Dashboard,
    };
    static template = "sale_management_renting.RentalFileUploadKanbanRenderer";
}

export const rentalFileUploadKanbanView = {
    ...saleFileUploadKanbanView,
    Renderer: RentalFileUploadKanbanRenderer,
};

registry.category("views").add("rental_file_upload_kanban", rentalFileUploadKanbanView);
