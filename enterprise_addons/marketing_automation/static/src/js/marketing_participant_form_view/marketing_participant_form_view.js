import { MarketingParticipantFormController } from "./marketing_participant_form_controller";
import { formView } from "@web/views/form/form_view";
import { registry } from "@web/core/registry";

export const MarketingParticipantFormView = {
    ...formView,
    Controller: MarketingParticipantFormController,
};

registry.category("views").add("marketing_participant_form_view", MarketingParticipantFormView);
