import { _t } from "@web/core/l10n/translation";
import { Component, useProps, t } from "@odoo/owl";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { useDropdownCloser } from "@web/core/dropdown/dropdown_hooks";
import { useSendToMarketingCampaign } from "@marketing_automation/js/hooks";
import { useService } from "@web/core/utils/hooks";

export class AddRecordToCampaign extends Component {
    static template = "marketing_automation.AddRecordToCampaign";
    static components = { DropdownItem };

    props = useProps({
        currentRecordModel: t.string(),
        currentResId: t.number(),
    });

    setup() {
        this.action = useService("action");
        this.sendToMarketingCampaign = useSendToMarketingCampaign();
        this.dropdownCloser = useDropdownCloser();
    }

    sendRecordToCampaign() {
        const resModel = this.props.currentRecordModel;
        const resIds = [this.props.currentResId];
        this.sendToMarketingCampaign(resModel, resIds, () => {
            this.dropdownCloser.closeAll();
        });
    }

    openParticipantView() {
        this.action.doAction({
            name: _t("Participants"),
            res_model: "marketing.participant",
            target: "current",
            domain: [
                ["res_id", "=", this.props.currentResId],
                ["model_name", "=", this.props.currentRecordModel],
            ],
            type: "ir.actions.act_window",
            views: [
                [false, "list"],
                [false, "form"],
            ],
        });
    }
}
