import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { registry } from "@web/core/registry";
import { markup, proxy, useProps } from "@odoo/owl";
import { standardActionServiceProps } from "@web/webclient/actions/action_plugin";
import { StockBarcodeMainScanner } from "../main_scanner/main_scanner";

export class MainMenu extends StockBarcodeMainScanner {
    static template = "stock_barcode.MainMenu";

    props = useProps(standardActionServiceProps);

    setup() {
        super.setup();
        const displayDemoMessage = this.props.action.params?.message_demo_barcodes || false;
        this.state = proxy({ ...super.state, displayDemoMessage });
    }

    removeDemoMessage() {
        const params = {
            title: _t("Don't show this message again"),
            body: _t(
                "Do you want to permanently remove this message ? " +
                    "It won't appear anymore, so make sure you don't need the barcodes sheet or you have a copy."
            ),
            confirm: () => {
                rpc("/stock_barcode/rid_of_message_demo_barcodes"); // Sets action message param false on server
                this.state.displayDemoMessage = false; // Remove message from current view
                this.props.action.params.message_demo_barcodes = false; // Remove message if using breadcrumbs
            },
            cancel: () => {},
            confirmLabel: _t("Remove it"),
            cancelLabel: _t("Leave it"),
        };
        this.dialogService.add(ConfirmationDialog, params);
    }

    /** Builds the barcode landing page bullet points, decribing features available depending on settings */
    get barcodeHomeHelper() {
        const tags = {
            bold_s: markup`<b>`,
            bold_e: markup`</b>`,
        };

        const bullets = [
            _t(
                "Scan a %(bold_s)sproduct%(bold_e)s or its %(bold_s)spackaging%(bold_e)s to locate it",
                tags
            ),
        ];
        // 2nd bullet point depends on which setting is activated
        if (this.packageEnabled && this.trackingEnabled) {
            bullets.push(
                _t(
                    "Scan a %(bold_s)stracking number%(bold_e)s or a %(bold_s)spackage%(bold_e)s to find a transfer",
                    tags
                )
            );
        } else if (this.packageEnabled) {
            bullets.push(_t("Scan a %(bold_s)spackage%(bold_e)s to find a transfer", tags));
        } else if (this.trackingEnabled) {
            bullets.push(_t("Scan a %(bold_s)stracking number%(bold_e)s to find a transfer", tags));
        }
        bullets.push(_t("Scan a %(bold_s)spicking%(bold_e)s to open it", tags));
        bullets.push(_t("Scan a %(bold_s)scontact%(bold_e)s to see their pending transfers", tags));
        if (this.locationsEnabled) {
            bullets.push(_t("Scan a %(bold_s)slocation%(bold_e)s to initiate a transfer", tags));
        }
        bullets.push(_t("Scan an %(bold_s)soperation type%(bold_e)s to start it", tags));
        return bullets;
    }

    get demoMessage() {
        const demo_link = _t("Download demo data sheet");
        const barcode_link = _t("Download operation barcodes");

        const sheet_s = markup`<a href="/stock_barcode/static/img/barcodes_demo.pdf" target="_blank" aria-label="${demo_link}" title="${demo_link}">`;
        const ops_s = markup`<a href="/stock_barcode/print_inventory_commands?barcode_type=barcode_commands_and_operation_types" target="_blank" aria-label="${barcode_link}" title="${barcode_link}">`;
        const sheet_e = markup`</a>`;
        const ops_e = markup`</a>`;

        return _t(
            "Print the %(sheet_s)sdemo data sheet%(sheet_e)s to test, or %(ops_s)sbarcodes%(ops_e)s for operations.",
            { sheet_s, sheet_e, ops_s, ops_e }
        );
    }
}

registry.category("actions").add("stock_barcode_main_menu", MainMenu);
