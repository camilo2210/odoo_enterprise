import { onWillStart, useProps, t } from "@odoo/owl";
import { CheckBox } from "@web/core/checkbox/checkbox";
import {
    ConfirmationDialog,
    confirmationDialogProps,
} from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";

const isValidTitle = (m) =>
    typeof m === "string" || (typeof m === "object" && typeof m.toString === "function");

export class ExtraProductDialog extends ConfirmationDialog {
    static template = "stock_barcode.ExtraProductDialog";
    static components = { ...ConfirmationDialog.components, CheckBox };
    props = useProps({
        ...confirmationDialogProps,
        products: t.instanceOf(Map),
        body: t
            .string()
            .optional(
                _t(
                    "Following scanned products are not reserved for this transfer. Are you sure you want to add them?"
                )
            ),
        title: t.customValidator(t.any(), isValidTitle).optional(_t("Add extra product?")),
    });

    setup() {
        super.setup();
        onWillStart(async () => {
            this.displayUOM = await user.hasGroup("uom.group_uom");
        });
    }

    onCheckboxChange(productData) {
        productData.confirmed = !productData.confirmed;
    }
}
