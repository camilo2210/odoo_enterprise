import { CampaignFormController } from "./marketing_campaign_form_controller";
import { formView } from "@web/views/form/form_view";
import { registry } from "@web/core/registry";

export const CampaignFormView = {
    ...formView,
    Controller: CampaignFormController,
};

registry.category("views").add("marketing_campaign_form_view", CampaignFormView);
