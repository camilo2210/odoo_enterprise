import { TestEPos } from "@point_of_sale/backend/test_epos/test_epos";
import { patch } from "@web/core/utils/patch";

patch(TestEPos.prototype, {
    async getPrinterDataEPos() {
        const printer = await super.getPrinterDataEPos(...arguments);
        return {
            ...printer,
            printer_type: printer.printer_type === "obox" ? "epson_epos" : printer.printer_type,
        };
    },
});
