import { Component, useProps, t } from "@odoo/owl";
import { usePrepDisplay } from "@pos_enterprise/app/services/preparation_display_service";
import { computeFontColor } from "@pos_enterprise/app/utils/utils";
import { PosPrepStage } from "@pos_enterprise/app/models/pos_preparation_stage";

export class Stages extends Component {
    static template = "pos_enterprise.Stages";
    props = useProps({
        stages: t.array(t.instanceOf(PosPrepStage)),
    });

    setup() {
        this.prepDisplay = usePrepDisplay();
    }

    getFontColor(bgColor) {
        return computeFontColor(bgColor);
    }

    orderCount(stageId) {
        const prepOrderIds = this.prepDisplay.activeLines.reduce((prepOrders, pl) => {
            if (pl.stage_id.id === stageId && this.prepDisplay.checkStateVisibility(pl)) {
                prepOrders.add(pl.prep_order_id.id);
            }
            return prepOrders;
        }, new Set());
        return prepOrderIds.size;
    }
    getStageStyle(stage) {
        if (this.prepDisplay.selectedStageId !== stage.id) {
            return "";
        }
        const color = stage.color || "#7b7f85";
        return `border-color: ${color}80; background-color: ${color}30;`;
    }
}
