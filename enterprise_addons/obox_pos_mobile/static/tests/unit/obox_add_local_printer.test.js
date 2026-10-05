import { expect, test } from "@odoo/hoot";
import { localPrinterDomain } from "@obox_pos_mobile/backend/obox_add_local_printer";

test("the device's Obox is matched on its serial number", () => {
    expect(localPrinterDomain("phone-1 ")).toEqual([
        ["type", "=", "printer"],
        ["obox_id.serial_number", "=", "PHONE-1"],
    ]);
});

test("every printer is matched when the serial number is unknown", () => {
    expect(localPrinterDomain(null)).toEqual([["type", "=", "printer"]]);
    expect(localPrinterDomain(undefined)).toEqual([["type", "=", "printer"]]);
    expect(localPrinterDomain("   ")).toEqual([["type", "=", "printer"]]);
});
