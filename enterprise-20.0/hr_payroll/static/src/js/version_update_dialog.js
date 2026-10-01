import { Component, signal, t, useProps } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export class VersionUpdateDialog extends Component {
    static template = "l10n_be_hr_payroll.VersionUpdateDialog";
    static components = { Dialog };

    props = useProps({
        cancel: t.function(),
        close: t.function(),
        confirm: t.function(),
        payslipsCount: t.number().optional(),
    });

    dateStart = signal(`${new Date().toISOString().slice(0, 8)}-01`);
    mode = signal("create_new_version");

    onApply = () => {
        this.props.confirm({
            dateStart: this.dateStart(),
            mode: this.mode(),
        });
        this.props.close();
    };

    onDiscard = () => {
        this.props.cancel();
        this.props.close();
    };
}
