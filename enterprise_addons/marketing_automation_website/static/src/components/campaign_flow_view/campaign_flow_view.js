import { _t } from "@web/core/l10n/translation";
import { CampaignFlowView } from "@marketing_automation/components/campaign_flow_view/campaign_flow_view";
import { patch } from "@web/core/utils/patch";

patch(CampaignFlowView.prototype, {
    setup() {
        super.setup();
        Object.assign(this.TRIGGER_ACTION_TYPES_DISPLAYS, {
            form_submit: _t("When Form Submitted"),
            page_visit: _t("When Pages Visited"),
        });
    },
});
