import { Field } from "@web/views/fields/field";
import { MrpTimer } from "@mrp/widgets/timer";
import { Component, t, useProps } from "@odoo/owl";

export class MrpWorkorder extends Component {
    static components = { Field, MrpTimer };
    static template = "mrp_workorder.WorkOrder";

    props = useProps({
        clickable: t.boolean(),
        record: t.object(),
        selectWorkcenter: t.function().optional(),
        sessionOwnerId: t.number().optional(),
    });

    get active() {
        return this.props.record.data.employee_ids.records.length !== 0;
    }

    get isComplete() {
        return this.props.record.data.state === "done";
    }

    get isEmployeeAssigned() {
        return this.props.record.data.employee_assigned_ids?.resIds.includes(
            this.props.sessionOwnerId
        );
    }

    get workcenter() {
        return this.props.record.data.workcenter_id;
    }

    onClick() {
        if (this.props.clickable) {
            this.clicked();
        }
    }

    clicked() {
        this.props.selectWorkcenter(this.workcenter.id, this.props.record.resId);
    }
}
