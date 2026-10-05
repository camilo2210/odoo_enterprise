import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

import { ViewButton } from "@web/views/view_button/view_button";
import { executeButtonCallback } from "@web/views/view_button/view_button_hook";

export class PayRunViewButton extends ViewButton {
    setup() {
        super.setup();
        this.dialog = useService("dialog");
    }

    /**
     * @override
     */
    async onClick(ev, newWindow) {
        if (this.props.attrs?.["confirm-inverted"]) {
            await executeButtonCallback(this.env.rootRef(), async () => {
                await new Promise((resolve) => {
                    const dialogProps = {
                        ...(this.props.clickParams["confirm-title"] && {
                            title: this.props.clickParams["confirm-title"],
                        }),
                        ...(this.props.clickParams["confirm-label"] && {
                            confirmLabel: this.props.clickParams["confirm-label"],
                        }),
                        ...(this.props.clickParams["cancel-label"] && {
                            cancelLabel: this.props.clickParams["cancel-label"],
                        }),
                        body: this.props.attrs["confirm-inverted"],
                        confirm: () => {},
                        cancel: () => super.onClick(ev, newWindow),
                    };
                    this.dialog.add(ConfirmationDialog, dialogProps, { onClose: resolve });
                });
            });
        } else {
            super.onClick(ev, newWindow);
        }
    }
}
