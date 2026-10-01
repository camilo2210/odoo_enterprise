import { t, useProps } from "@odoo/owl";
import { CopyButton, copyButtonProps } from "@web/core/copy_button/copy_button";
import {
    CopyClipboardButtonField,
    copyClipboardButtonField,
} from "@web/views/fields/copy_clipboard/copy_clipboard_field";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class SaveAndCopyButton extends CopyButton {
    props = useProps({
        ...copyButtonProps,
        record: t.object(),
    });

    setup() {
        super.setup();
        this.orm = useService("orm");
    }

    async onClick() {
        const isSaved = await this.props.record.model.root.save();
        if (!isSaved) {
            return;
        }
        await this.orm.call(
            "hr.contract.salary.offer",
            "check_simulation_required_fields",
            [[this.props.record.resId]],
        );
        return super.onClick();
    }
}

export class SaveAndCopyToClipboardButtonField extends CopyClipboardButtonField{
    static template = "web.SaveAndCopyToClipboardButtonField";
    static components = { SaveAndCopyButton };
};

const saveAndCopyToClipboardButtonField = {
    ...copyClipboardButtonField,
    component: SaveAndCopyToClipboardButtonField,
};

registry.category("fields").add("SaveAndCopyToClipboardButton", saveAndCopyToClipboardButtonField);
