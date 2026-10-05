import { useProps, t } from "@odoo/owl";
import {
    SelectCreateDialog,
    selectCreateDialogProps,
} from "@web/views/view_dialogs/select_create_dialog"

export class SelectCreateAutoPlanDialog extends SelectCreateDialog {
    static template = "project_enterprise.SelectCreateAutoPlanDialog";
    props = useProps({
        ...selectCreateDialogProps,
        onSelectedNoSmartSchedule: t.function(),
    });

    select(resIds) {
        if (this.props.onSelectedNoSmartSchedule) {
            this.executeOnceAndClose(() => this.props.onSelectedNoSmartSchedule(resIds));
        }
    }

    selectWithSmartSchedule(resIds) {
        if (this.props.onSelected) {
            this.executeOnceAndClose(() => this.props.onSelected(resIds));
        }
    }
}
