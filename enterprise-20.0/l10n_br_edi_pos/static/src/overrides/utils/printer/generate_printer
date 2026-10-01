import { patch } from "@web/core/utils/patch";
import { GeneratePrinterData } from "@point_of_sale/app/utils/printer/generate_printer_data";

/**
 * This class is a JS copy of the class PosOrderReceipt in Python.
 */
patch(GeneratePrinterData.prototype, {
    generateReceiptData() {
        const data = super.generateReceiptData(...arguments);
        if (this.order.company.country_id.code !== "BR") {
            return data;
        }

        function formatAddress(address) {
            if (!address) {
                return "";
            }
            return [
                address["street"],
                address["number"],
                address["neighborhood"],
                address["cityName"],
                address["state"],
            ]
                .filter((s) => s)
                .join(", ");
        }

        const partner = this.order.partner_id;
        const metadata = partner?.available_additional_identifiers_metadata || {};
        const identifiers = Object.keys(partner?.additional_identifiers || {});
        if (partner?.vat) {
            // the CNPJ, kept in the vat, outranks the additional identifiers
            identifiers.unshift("BR_TIN");
        }
        const [key] = identifiers.sort(
            (a, b) => (metadata[a]?.sequence ?? 100) - (metadata[b]?.sequence ?? 100)
        );
        if (metadata[key]?.label) {
            data.extra_data.partner_vat_label = metadata[key].label;
        }

        const env = this.order.company.l10n_br_avalara_environment;
        data.conditions.l10n_br_is_nfce = this.order.config.l10n_br_is_nfce;
        data.conditions.l10n_br_avalara_environment_sandbox = env === "sandbox";
        let establishment_full_address = "";
        let entity_full_address = "";
        let stateTaxId = "";
        let qrCodeData = null;

        if (this.order.l10n_br_edi_avatax_data?.header) {
            const header = this.order.l10n_br_edi_avatax_data.header;
            const locations = header.locations || {};
            const establishment = locations.establishment;
            stateTaxId = establishment?.stateTaxId || "";
            establishment_full_address = formatAddress(establishment?.address);
            entity_full_address = formatAddress(locations.entity?.address);
            qrCodeData = header.goods?.nfceQrCode || null;
        }

        data.extra_data.l10n_br_edi_avatax_data = {
            ...this.l10n_br_edi_avatax_data,
            establishment_full_address: establishment_full_address,
            entity_full_address: entity_full_address,
            state_tax_id: stateTaxId,
            items_count: this.order.l10nBrEdiGetNrUniqueItems(),
            formatted_key: this.order.l10nBrEdiGetFormattedAccessKey(),
            header: this.order.l10n_br_edi_avatax_data?.header || {},
            qr_code_data: this.generateQrCode(qrCodeData), // this.order.l10nBrEdiGetNFCeQRSrc() returns /report/barcode/QR////
        };

        return data;
    },
});
