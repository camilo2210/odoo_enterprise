import { Component, proxy, t, useProps } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

export class InputDialog extends Component {
    static components = { Dialog };
    static template = "spreadsheet_edition.InputDialog";

    props = useProps({
        close: t.function(), // injected by the dialog service
        body: t.string(),
        inputType: t.string().optional(),
        inputValue: t.or([t.string(), t.number()]).optional(),
        confirm: t.function().optional(),
        title: t.string().optional(),
    });

    setup() {
        this.state = proxy({
            inputValue: this.props.inputValue,
            error: "",
        });
    }

    get defaultTitle() {
        return _t("Odoo Spreadsheet");
    }

    confirm() {
        const convertedValue = this.convertInputValue(this.state.inputValue);

        if (this.props.inputType === "number" && isNaN(convertedValue)) {
            this.state.error = _t("Please enter a valid number.");
            return;
        }

        this.props.close();
        this.props.confirm?.(convertedValue);
    }

    convertInputValue(value) {
        if (this.props.inputType === "number") {
            return parseInt(value, 10);
        }
        return value;
    }
}
