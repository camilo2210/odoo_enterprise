import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { BurgerMenuDialog } from "@point_of_sale/app/components/navbar/navbar";
import { DateSelectionPopup } from "@l10n_at_pos/app/components/popup/date_selection_popup/date_selection_popup";

patch(BurgerMenuDialog.prototype, {
    setup() {
        super.setup(...arguments);
        this.mapNames = {
            gross_amount_standard: _t("Gross Amount Standard"),
            gross_amount_reduced_1: _t("Gross Amount Reduced 1"),
            gross_amount_reduced_2: _t("Gross Amount Reduced 2"),
            gross_amount_special: _t("Gross Amount Special"),
            gross_amount_zero: _t("Gross Amount Zero"),
        };
    },

    get menuLabel() {
        return _t("Monthly / Yearly Receipts");
    },

    printClosingReceipts() {
        this.dialog.add(DateSelectionPopup, {
            title: _t("Print closing receipts"),
            getPayload: async (payload) => {
                const res = await this.pos.data.call(
                    "pos.config",
                    "fetch_fiskaly_closing_receipt_data",
                    [[this.pos.session.config_id.id], payload.selectedDate, payload.period]
                );

                if (res["data"].length && this.pos.ticketPrinter.defaultPrinter) {
                    // prepare title based on selection
                    const data = res["data"][0];
                    const date = new Date(`${payload.selectedDate}-01`);
                    const monthName = date.toLocaleString("default", { month: "long" });
                    const year = date.getFullYear();
                    const title = payload.period == "monthly" ? `${monthName} ${year}` : `${year}`;

                    // prepare qrImage data
                    const codeWriter = new window.ZXing.BrowserQRCodeSvgWriter();
                    const qr_code_svg = new XMLSerializer().serializeToString(
                        codeWriter.write(data["qr_code_data"], 150, 150)
                    );
                    const qrImage = "data:image/svg+xml;base64," + window.btoa(qr_code_svg);

                    const receipt = await this.pos.ticketPrinter.generateIframe(
                        "l10n_at_pos.ClosingReceipts",
                        {
                            config: this.pos.session.config_id,
                            heading: title,
                            data: data,
                            qrImage: qrImage,
                            raw_data: data["schema"]["raw"],
                            mappedName: this.mapNames,
                        }
                    );
                    await this.pos.ticketPrinter.printWithFallback({ iframe: receipt });
                } else {
                    if (res["message"] !== "success") {
                        return this.dialog.add(AlertDialog, {
                            title: _t("No data found!"),
                            body: res["message"],
                        });
                    }
                    // Message success means we got the data still here only means no printer connected
                    this.dialog.add(AlertDialog, {
                        title: _t("Printing Error"),
                        body: _t("No printer connected to print the receipt"),
                    });
                }
            },
        });
    },
});
