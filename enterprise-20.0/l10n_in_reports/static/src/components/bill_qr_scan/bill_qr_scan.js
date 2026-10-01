import { useSubEnv } from "@web/owl2/utils";
import {
    AccountMoveKanbanController,
} from "@account/views/account_move_kanban/account_move_kanban_controller";
import {
    AccountMoveListController,
} from "@account/views/account_move_list/account_move_list_controller";
import { Component, onWillStart, t, usePlugin, useProps } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useBus } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { isBarcodeScannerSupported } from "@web/core/barcode/barcode_video_scanner";
import { ManualBarcodeScanner } from "@barcodes/components/manual_barcode";
import { user } from "@web/core/user";
import { ORM } from "@web/core/orm_plugin";
import { DialogPlugin } from "@web/core/dialog/dialog_plugin";
import { NotificationPlugin } from "@web/core/notifications/notification_plugin";
import { UIPlugin } from "@web/core/ui/ui_plugin";
import { ActionPlugin } from "@web/webclient/actions/action_plugin";
import { BarcodePlugin } from "@barcodes/barcode_plugin";

export class BillQrScan extends Component {

    static template = "l10n_in_reports.billScanInput";
    static components = { Dialog };
    props = useProps({ close: t.function() });

    actionPlugin = usePlugin(ActionPlugin);
    barcodePlugin = usePlugin(BarcodePlugin);
    dialog = usePlugin(DialogPlugin);
    notification = usePlugin(NotificationPlugin);
    orm = usePlugin(ORM);
    ui = usePlugin(UIPlugin);

    setup() {
        useBus(this.barcodePlugin.bus, "barcode_scanned", (ev) => this._onBarcodeScanned(ev));
        onWillStart(async () => {
            this.isMobileScanner = isBarcodeScannerSupported();
        });
    }

    async openMobileScanner() {
        this.dialog.add(ManualBarcodeScanner, {
            facingMode: "environment",
            onResult: (barcode) => {
                if (barcode) {
                    this.barcodePlugin.bus.trigger("barcode_scanned", { barcode });
                    if ("vibrate" in window.navigator) {
                        window.navigator.vibrate(100);
                    }
                } else {
                    this.notification.add(_t("Please, Scan again!"), { type: "warning" });
                }
            },
            placeholder: _t("Enter QR / IRN Manually"),
            onError: () => {},
        });
    }

    async _onBarcodeScanned(ev) {
        this.ui.block();
        try {
            const res = await this.orm.call(
                "account.move", "l10n_in_get_bill_from_qr_raw", [], { qr_raw: ev?.detail?.barcode }
            );
            if (res.action) {
                return this.actionPlugin.doAction(res.action);
            }
            this.notification.add(res.warning, { type: "warning" });
        } finally {
            this.ui.unblock();
        }
    }
}
registry.category('actions').add('l10n_in_bill_qr_code_scan', BillQrScan);

export function qrBillScannerController() {
    return {
        setup() {
            super.setup();
            this.dialog = usePlugin(DialogPlugin);
            this.orm = usePlugin(ORM);
            useSubEnv({
                openScanWizard: this.openScanWizard.bind(this),
            });
            onWillStart(async () => {
                const currentCompanyId = user.activeCompany.id;
                this.data = await this.orm.searchRead("res.company", [["id", "=", currentCompanyId]], ["country_code"])
                this.countryCode = this.data[0].country_code;
            });
        },
    
        openScanWizard() {
            this.dialog.add(BillQrScan);
        },

        get isButtonDisplayed() {
            return this.countryCode == 'IN' && ["in_invoice", "in_refund"].includes(this.props.context.default_move_type ?? '')
        },
    }
}

patch(AccountMoveKanbanController.prototype, qrBillScannerController());
patch(AccountMoveListController.prototype, qrBillScannerController());
