import { Component, onMounted, proxy, signal, t, useProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class ControlPanelButtons extends Component {
    static template = "mrp_workorder.ControlPanelButtons";

    props = useProps({
        activeWorkcenter: t.or([t.boolean(), t.number()]),
        productionCount: t.number(),
        selectWorkcenter: t.function(),
        toggleWorkcenter: t.function(),
        workcenters: t.array(),
        workorders: t.array(),
        relevantCount: t.number(),
        adminWorkorders: t.array(),
        hideNewWorkcenterButton: t.boolean(),
    });

    workcentersContainerRef = signal.ref();
    workcentersRef = signal.ref();
    workcenterDropdownMenuRef = signal.ref();

    setup() {
        this.state = proxy({ workCenterOverflow: false });
        this.ui = useService("ui");
        onMounted(() => {
            //TODO CLPI / SVS - Set active class on dropdown-toggle if
            // workcenter active inside dropdown-menu
            // We should also run moveWorkcenterButtons() when a
            // workcenter is added
            if (!this.ui.isSmall) {
                this.moveWorkcenterButtons();
            }
        });
    }

    get workcenterButtons() {
        const workcenterButtons = {};
        let productionCount = this.props.productionCount;
        let adminCount = 0;
        for (const { id, display_name, working_state } of this.props.workcenters) {
            workcenterButtons[id] = { count: 0, name: display_name, working_state: working_state };
        }
        for (const workorder of this.props.workorders) {
            if (workorder.data.state === "cancel") {
                continue;
            }
            const button = workcenterButtons[workorder.data.workcenter_id.id];
            if (button) {
                button.count++;
            }
            if (this.props.adminWorkorders.includes(workorder.resId)) {
                adminCount++;
            }
        }
        if (this.props.activeWorkcenter > 0 && workcenterButtons[this.props.activeWorkcenter]) {
            workcenterButtons[this.props.activeWorkcenter].count = this.props.relevantCount;
        } else if (this.props.activeWorkcenter === 0) {
            productionCount = this.props.relevantCount;
        } else if (this.props.activeWorkcenter === -1) {
            adminCount = this.props.relevantCount;
        }
        if (workcenterButtons[0]) {
            workcenterButtons[0].count = productionCount;
        }
        if (workcenterButtons[-1]) {
            workcenterButtons[-1].count = adminCount;
        }
        return this.props.workcenters.map((wc) => [String(wc.id), workcenterButtons[wc.id]]);
    }

    moveWorkcenterButtons() {
        // Move workcenters in a dropdown-menu to avoid overflow
        const workcenterButtons = [];
        if (this.workcentersContainerRef().offsetWidth < this.workcentersRef().offsetWidth) {
            this.state.workCenterOverflow = true;
        }
        while (this.workcentersContainerRef().offsetWidth < this.workcentersRef().offsetWidth) {
            const lastWorkCenterBtn = [
                ...this.workcentersRef().querySelectorAll(".o_work_center_btn"),
            ].at(-1);
            workcenterButtons.unshift(lastWorkCenterBtn);
            lastWorkCenterBtn.remove();
        }
        workcenterButtons.forEach((button) => {
            button.classList.add("dropdown-item", "justify-content-between", "py-2");
            button.classList.remove("p-2", "btn", "btn-light");
            this.workcenterDropdownMenuRef().insertBefore(
                button,
                this.workcenterDropdownMenuRef().querySelector(".o_work_center_add")
            );
        });
    }
}
