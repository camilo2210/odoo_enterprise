import { registry } from "@web/core/registry";
import { saleFileUploadListView } from "@sale/views/sale_file_upload_list/sale_file_upload_list_view";
import { SaleFileUploadListRenderer } from "@sale/views/sale_file_upload_list/sale_file_upload_list_renderer";
import { Dashboard } from "@sale_renting/js/dashboard/dashboard";

export class RentalFileUploadListRenderer extends SaleFileUploadListRenderer {
    static components = {
        ...SaleFileUploadListRenderer.components,
        Dashboard,
    };
    static template = "sale_management_renting.RentalFileUploadListRenderer";
}

export const rentalFileUploadListView = {
    ...saleFileUploadListView,
    Renderer: RentalFileUploadListRenderer,
};

registry.category("views").add("rental_file_upload_list", rentalFileUploadListView);
