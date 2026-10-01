import {
    ConfirmationDialog,
    confirmationDialogProps,
} from "@web/core/confirmation_dialog/confirmation_dialog";
import { location } from "@web/core/browser/browser";
import { user } from "@web/core/user";
import { useService, useBus } from "@web/core/utils/hooks";
import { onWillStart, useProps, proxy, t } from "@odoo/owl";

export class MrpEmployeeDialog extends ConfirmationDialog {
    static template = "mrp_workorder.MrpEmployeeDialog";
    props = useProps({
        ...confirmationDialogProps,
        employees: t.object(),
        setConnectedEmployees: t.function(),
        getAllEmployees: t.function(),
    });

    setup() {
        super.setup();
        this.imageBaseURL = `${location.origin}/web/image?model=hr.employee.public&field=avatar_128&id=`;
        this.selected = proxy({ ids: this.props.employees.connected.map((item) => item.id) });
        this.orm = useService("orm");
        this.barcode = useService("barcode");
        this.hasEmployees = this.props.employees.all.length > 0;
        this.action = useService("action");
        useBus(this.barcode.bus, "barcode_scanned", (event) =>
            this._onBarcodeScanned(event.detail.barcode)
        );
        onWillStart(async () => {
            this.isHrUser = await user.hasGroup("hr.group_hr_user");
        });
    }

    toggleEmployee(id) {
        if (this.selected.ids.includes(id)) {
            this.selected.ids.splice(this.selected.ids.indexOf(id), 1);
        } else {
            this.selected.ids.push(id);
        }
    }

    async confirm() {
        await this.props.setConnectedEmployees(this.selected.ids);
        return this.props.close();
    }

    async createEmployee() {
        const newEmployeeId = await this.orm.call("res.users", "action_create_employee", [
            user.userId,
        ]);
        await this.props.getAllEmployees();
        await this.props.setConnectedEmployees(newEmployeeId);
        return this.props.close();
    }

    async _onBarcodeScanned(barcode) {
        const employee = await this.orm.call("mrp.workcenter", "get_employee_barcode", [barcode]);
        if (employee) {
            this.toggleEmployee(employee);
        }
    }
}
