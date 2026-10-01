import { CrmControlPanel } from "@crm/views/crm_control_panel";
import { CrmSearchModel } from "@crm/views/crm_search_model";
import { cohortView } from "@web_cohort/cohort_view";
import { registry } from "@web/core/registry";

export const crmCohortView = {
    ...cohortView,
    ControlPanel: CrmControlPanel,
    SearchModel: CrmSearchModel,
};

registry.category("views").add("crm_cohort", crmCohortView);
