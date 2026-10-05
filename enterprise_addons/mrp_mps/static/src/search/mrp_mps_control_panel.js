import { ControlPanel } from "@web/search/control_panel/control_panel";
import { useBus } from "@web/core/utils/hooks";

export class MrpMpsControlPanel extends ControlPanel {
    setup() {
        super.setup();
        useBus(this.env.searchModel, "update", () => {
            this.env.config.offset = 0;
            this.env.config.limit = this.env.defaultPageLimit;
            this.env.model.load(this.env.searchModel.domain, this.env.config.offset, this.env.config.limit);
        });
    }
}
