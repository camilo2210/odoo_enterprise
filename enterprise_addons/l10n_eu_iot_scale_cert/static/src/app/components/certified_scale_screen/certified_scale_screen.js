import { useSubEnv } from "@web/owl2/utils";
import { Component, useProps, types as t } from "@odoo/owl";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";

// This is functionally identical to the base ScaleScreen component,
// other than the fact that errors are returned as zero weight, preventing
// an order line from being added.
// Having a separate copy allows us to keep a certified version that will only change
// if absolutely necessary, whilst the base component is free to change.

export class CertifiedScaleScreen extends Component {
    static template = "l10n_eu_iot_scale_cert.CertifiedScaleScreen";
    static components = { Dialog };
    props = useProps({
        getPayload: t.function([t.number()]),
        close: t.function([]),
    });

    setup() {
        this.dialog = useService("dialog");
        this.uiService = useService("ui");
        this.pos = usePos();
        this.scale = this.pos.scale;
        this.scale.setErrorCallback(this.onError.bind(this));
        useSubEnv({ dialogData: { ...this.env.dialogData, close: this.close.bind(this) } });
    }

    confirm() {
        this.props.getPayload(this.scale.confirmWeight());
        this.close();
    }

    close() {
        this.props.close();
        this.scale.product = null;
    }

    onError(message) {
        this.props.getPayload(0);
        this.dialog.add(
            AlertDialog,
            {
                title: _t("Scale error"),
                body: message,
            },
            { onClose: this.close.bind(this) }
        );
    }
}
