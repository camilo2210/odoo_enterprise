import { patch } from "@web/core/utils/patch";
import { GeneratePrinterData } from "@point_of_sale/app/utils/printer/generate_printer_data";

/**
 * This class is a JS copy of the class PosOrderReceipt in Python.
 */
patch(GeneratePrinterData.prototype, {
    generateReceiptData() {
        const data = super.generateReceiptData(...arguments);
        const isCountryGermany = this.order.isCountryGermany();

        data.conditions.code_de = isCountryGermany;
        if (!isCountryGermany) {
            return data;
        }

        if (!this.order.getTssId()) {
            data.conditions.l10n_de_test_env = true;
            return data;
        }

        if (!this.order.isTransactionFinished()) {
            data.conditions.l10n_de_error = true;
            return data;
        }

        data.extra_data["tss"] = this.getTssValues();
        return data;
    },

    getTssValues() {
        const order = this.order;
        return [
            { name: "TSE-Transaktion", value: order.l10n_de_fiskaly_transaction_number },
            { name: "Bonnummer", value: order.id },
            {
                name: "TSE-Start",
                value: order.l10n_de_fiskaly_time_start
                    ?.toUTC()
                    .toFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'"),
            },
            {
                name: "TSE-Stop",
                value: order.l10n_de_fiskaly_time_end
                    ?.toUTC()
                    .toFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'"),
            },
            { name: "TSE-Seriennummer", value: order.l10n_de_fiskaly_certificate_serial },
            { name: "TSE-Zeitformat", value: order.l10n_de_fiskaly_timestamp_format },
            { name: "TSE-Signatur", value: order.l10n_de_fiskaly_signature_value },
            { name: "TSE-Hashalgorithmus", value: order.l10n_de_fiskaly_signature_algorithm },
            { name: "TSE-PublicKey", value: order.l10n_de_fiskaly_signature_public_key },
            { name: "Client Serial No.", value: order.l10n_de_fiskaly_client_serial_number },
        ].map(({ name, value }) => ({ name, value: value || "" }));
    },
});
