import { _t } from "@web/core/l10n/translation";
import { localization } from "@web/core/l10n/localization";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { usePopover } from "@web/core/popover/popover_hook";
import { useService } from "@web/core/utils/hooks";
import { Component, markup, signal, t, useProps } from "@odoo/owl";

const isNonEmptyObject = (obj) => obj && Object.keys(obj).length > 0;

class TransactionDetailsPopover extends Component {
    static template = "account_accountant.TransactionDetailsPopover";

    props = useProps({
        formattedData: t.string(),
        setOverPopover: t.function(),
        close: t.function().optional(),
    });
}

class TransactionDetailsField extends Component {
    static template = "account_accountant.TransactionDetailsField";
    static components = { Popover: TransactionDetailsPopover };

    props = useProps(standardFieldProps);

    previewRef = signal.ref();

    setup() {
        const position = localization.direction === "rtl" ? "bottom" : "left";
        this.popover = usePopover(TransactionDetailsPopover, { position });
        this.orm = useService("orm");
        this.hideTimeout = null;
        this.isOverPopover = false;
    }

    get hasData() {
        return isNonEmptyObject(this.props.record.data[this.props.name]);
    }

    async showPopup() {
        if (this.popover.isOpen || !this.hasData) {
            return;
        }

        const formattedData = await this.orm.call(
            this.props.record.resModel,
            "format_transaction_details",
            [this.props.record.resId],
            { context: this.props.record.context }
        );

        if (formattedData) {
            this.popover.open(this.previewRef(), {
                formattedData: markup(formattedData),
                setOverPopover: this.setOverPopover.bind(this),
            });
        }
    }

    hidePopup() {
        this.hideTimeout = setTimeout(() => {
            if (!this.previewRef()?.matches(":hover") && !this.isOverPopover) {
                this.popover.close();
            }
        }, 100);
    }

    setOverPopover(value) {
        this.isOverPopover = value;
        if (!value) {
            this.hidePopup();
        }
    }
}

registry.category("fields").add("formatted_transaction_details", {
    component: TransactionDetailsField,
    displayName: _t("Formatted Transaction Details"),
    supportedTypes: ["json"],
});
