import { ControlPanel } from "@web/search/control_panel/control_panel";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";

export class PosAppointmentControlPanel extends ControlPanel {
    static template = "pos_appointment.PosAppointmentControlPanel";
    setup() {
        super.setup(...arguments);
        this.ui = useService("ui");
        this.pos = usePos();
    }
    switchView(viewType, newWindow) {
        const searchModel = this.env.searchModel;
        const filterNamesToDisable = ["date_filter", "hour_filter"];
        const filtersToDisable = Object.values(searchModel.searchItems).filter(
            (sm) =>
                filterNamesToDisable.includes(sm.name) &&
                searchModel.query.some((q) => q.searchItemId === sm.id)
        );
        for (const filter of filtersToDisable) {
            searchModel.toggleSearchItem(filter.id);
        }
        super.switchView(...arguments);
    }
}
