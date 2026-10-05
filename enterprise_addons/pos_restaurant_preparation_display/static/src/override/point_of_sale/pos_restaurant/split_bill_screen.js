import { patch } from "@web/core/utils/patch";
import { SplitBillScreen } from "@pos_restaurant/app/screens/split_bill_screen/split_bill_screen";

patch(SplitBillScreen.prototype, {
    getExtraValues(prepLine) {
        return {
            ...super.getExtraValues(prepLine),
            stage_id: prepLine.stage_id,
            last_stage_id: prepLine.last_stage_id,
            todo: prepLine.todo,
            last_stage_change: prepLine.last_stage_change,
        };
    },
});
