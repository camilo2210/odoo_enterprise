/** @odoo-module */

import { SelectDefaultPrinterPopup } from "@point_of_sale/app/components/popups/select_default_printer_popup/select_default_printer_popup";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";

patch(SelectDefaultPrinterPopup.prototype, {
    setup() {
        super.setup();
        this.dialog = useService("dialog");
        this.pos = usePos();
        this.state.selectedId = this.pos.ticketPrinter?.defaultPrinter?.id ?? null;
    },
    confirmSelection() {
        if (!this.state.selectedId) {
            return;
        }
        const printers = this.props.receipt_printers;
        // check if any fiscal printer exists
        const hasFiscalPrinter = printers.some((p) => p.printer_type === "it_fiscal_printer");
        // get selected printer
        const selectedPrinter = printers.find((p) => p.id === Number(this.state.selectedId));
        // if fiscal printer exists but selected one is not fiscal → show warning
        if (hasFiscalPrinter && selectedPrinter?.printer_type !== "it_fiscal_printer") {
            this.dialog.add(AlertDialog, {
                title: _t("Invalid Printer Selection"),
                body: _t(
                    "When a fiscal printer is available among the receipt printers, the default printer must be a fiscal printer."
                ),
            });
            return;
        }
        super.confirmSelection();
    },
});
