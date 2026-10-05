import { patch } from "@web/core/utils/patch";
import { GeneratePrinterData } from "@point_of_sale/app/utils/printer/generate_printer_data";

/**
 * This class is a JS copy of the class PosOrderReceipt in Python.
 */
patch(GeneratePrinterData.prototype, {
    generateReceiptData() {
        const data = super.generateReceiptData(...arguments);
        data.conditions.code_ke = this.company.country_id.code === "KE";

        if (data.conditions.code_ke && this.order.l10n_ke_order_json) {
            try {
                const parsed =
                    typeof value === "object"
                        ? this.order.l10n_ke_order_json
                        : JSON.parse(this.order.l10n_ke_order_json);
                const taxTypes = { B: "16%", E: "8%", C: "0%", D: "Non-VAT", A: "Exempt" };
                const qrcode = this.generateQrCode(this.order.l10n_ke_edi_oscu_pos_qrurl);
                const serial = this.order.company.l10n_ke_oscu_serial_number;
                const sign = this.order.is_refund_or_negative() ? -1 : 1;
                const taxes = Object.entries(taxTypes).reduce((acc, [type, rate]) => {
                    const taxableAmount = (parsed[`taxblAmt${type}`] || 0.0) * sign;
                    const taxAmount = (parsed[`taxAmt${type}`] || 0.0) * sign;
                    const totalAmount = taxableAmount + taxAmount;

                    acc.push({
                        rate: rate,
                        taxable_amount: taxableAmount,
                        tax_amount: taxAmount,
                        total_amount: totalAmount,
                    });

                    return acc;
                }, []);

                taxes.push({
                    rate: "Total",
                    taxable_amount: parsed["totTaxblAmt"] * sign,
                    tax_amount: parsed["totTaxAmt"] * sign,
                    total_amount: parsed["totAmt"] * sign,
                });

                for (const t of taxes) {
                    t.taxable_amount = this.formatCurrency(t.taxable_amount);
                    t.tax_amount = this.formatCurrency(t.tax_amount);
                    t.total_amount = this.formatCurrency(t.total_amount);
                }

                data.image.l10n_ke_edi_oscu_pos_qrsrc = qrcode;
                data.extra_data.l10n_ke_edi_oscu_taxes = taxes.length ? taxes : false;
                data.extra_data.l10n_ke_oscu_serial_number = serial;
                return data;
            } catch {
                return data;
            }
        }

        return data;
    },
});
