import BarcodeModel from "@stock_barcode/models/barcode_model";

import { patch } from "@web/core/utils/patch";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";

patch(BarcodeModel.prototype, {
    /**
     * The purpose of this extension is to allow the user to create the product for the barcode data
     * if no product found based on barcode lookup!
     *
     * @override
     */
    async _noProductToast(barcodeData) {
        const barcodeDataToPass = {
            barcode: barcodeData.barcode,
            content: barcodeData.error,
            callback: async () => {
                barcodeData && (await this.createNewProductLine(barcodeData));
            },
        };
        this.barcodeService.bus.trigger("create_product", { barcodeData: barcodeDataToPass });
    },

    // method for the "Create Product" button in settings
    async openProductForm() {
        return await this.action.doAction(
            "stock_barcode_barcodelookup.stock_barcodelookup_product_product_action",
            {
                additionalContext: {
                    default_is_storable: true,
                    dialog_size: "medium",
                    skip_barcode_check: true,
                },
                props: {
                    onSave: async (_record) => {
                        this.notification(_t("Product created successfully"), { type: "success" });
                        return this.action.doAction({ type: "ir.actions.act_window_close" });
                    },
                },
            }
        );
    },

    async createNewProductLine(barcodeData) {
        const barcodes_by_model = { "product.product": [barcodeData.barcode] };
        const params = { barcodes_by_model };
        try {
            const result = await rpc("/stock_barcode/get_specific_barcode_data", params);
            if (Object.keys(result).length === 0) {
                const message = _t("No record found for the specified barcode");
                return this.notification(message, {
                    title: _t("Inconsistent Barcode"),
                    type: "danger",
                });
            }
            this.cache.setCache(result);

            // modifying the barcodeData
            const [productRecord] = result["product.product"];
            barcodeData.match = true;
            barcodeData.quantity = 1;
            barcodeData.product = productRecord;
            const fieldsParams = this._convertDataToFieldsParams(barcodeData);
            if (barcodeData.uom) {
                fieldsParams.uom = barcodeData.uom;
            }
            const currentLine = await this.createNewLine({ fieldsParams });
            if (currentLine) {
                this._selectLine(currentLine);
            }
            this.trigger("update");
            return true;
        } catch (error) {
            return this.notification(error, {
                title: _t("RPC Error"),
                type: "danger",
            });
        }
    },

    get isValidForBarcodeLookup() {
        return true;
    },
});
