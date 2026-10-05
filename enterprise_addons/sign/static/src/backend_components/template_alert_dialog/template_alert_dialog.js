import { AlertDialog, alertDialogProps } from "@web/core/confirmation_dialog/confirmation_dialog";
import { useProps, t } from "@odoo/owl";

export class TemplateAlertDialog extends AlertDialog {
    props = useProps({
        ...alertDialogProps,
        body: t.string().optional(),
    });
    static template = "sign.TemplateAlertDialog";
}
