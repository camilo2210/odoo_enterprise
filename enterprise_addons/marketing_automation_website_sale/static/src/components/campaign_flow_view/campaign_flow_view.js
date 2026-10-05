import { _t } from "@web/core/l10n/translation";
import { CampaignFlowView } from "@marketing_automation/components/campaign_flow_view/campaign_flow_view";
import { patch } from "@web/core/utils/patch";

patch(CampaignFlowView.prototype, {
    setup() {
        super.setup();
        Object.assign(this.TRIGGER_ACTION_TYPES_DISPLAYS, {
            product_bought: _t("When Product(s) Bought"),
            product_cart: _t("When Product(s) in Cart"),
        });
    },
});
