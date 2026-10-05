import { CrmControlPanel } from "@crm/views/crm_control_panel";
import { CrmSearchModel } from "@crm/views/crm_search_model";
import { mapView } from "@web_map/map_view/map_view";
import { registry } from "@web/core/registry";

export const crmMapView = {
    ...mapView,
    ControlPanel: CrmControlPanel,
    SearchModel: CrmSearchModel,
};

registry.category("views").add("crm_map", crmMapView);
