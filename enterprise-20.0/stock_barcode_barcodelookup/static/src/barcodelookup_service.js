import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { BarcodeParser } from "@barcodes/js/barcode_parser";
import { user } from "@web/core/user";

export class BarcodeLookupServiceClass {
    constructor(env, services) {
        this.env = env;
        this.orm = services.orm;
        this.barcode = services.barcode;
        this.notification = services.notification;
        this.action = services.action;
    }

    async setup() {
        const currentCompanyId = user.activeCompany.id;
        this.hasAccess = await user.hasGroup("product.group_product_manager");

        if (this.hasAccess) {
            try {
                const companyData = await this.orm.searchRead(
                    "res.company",
                    [["id", "=", currentCompanyId]],
                    ["nomenclature_id"]
                );
                const nomenclatureId = companyData?.[0]?.nomenclature_id?.[0];
                this.isGS1 = false;
                if (nomenclatureId) {
                    this.nomenclature = await BarcodeParser.fetchNomenclature(
                        this.orm,
                        nomenclatureId
                    );
                    this.isGS1 = this.nomenclature.is_gs1_nomenclature || false;
                    this.parser = new BarcodeParser({ nomenclature: this.nomenclature });
                }
            } catch {
                this.nomenclature = false;
                this.isGS1 = false;
                this.parser = false;
            }
        }

        this.barcode.bus.addEventListener("create_product", async (ev) => {
            const barcodeData = ev.detail ? ev.detail.barcodeData : null;
            if (barcodeData && barcodeData.barcode) {
                if (this.allowProductCreation(barcodeData.barcode)) {
                    return this.notification.add(barcodeData.content, {
                        type: "danger",
                        buttons: [
                            {
                                name: _t("Create New Product"),
                                primary: false,
                                onClick: () => this.openProductForm(barcodeData),
                            },
                        ],
                    });
                } else {
                    // return simple notification if product creation is not allowed
                    return this.notification.add(barcodeData.content, { type: "danger" });
                }
            }
        });
    }

    allowProductCreation(rawBarcode) {
        // If GS1 barcode, convert barcode from GTIN-14 to EAN-13
        // Valid only if there is a zero at the start
        if (!this.parser) {
            return false;
        }

        let barcode = rawBarcode;
        if (this.isGS1 && rawBarcode[0] === "0" && rawBarcode.length === 14) {
            barcode = rawBarcode.slice(1, 14);
        }
        const validEncoding = ["ean8", "ean13", "upca"].some((encoding) =>
            this.parser.check_encoding(barcode, encoding)
        );
        return this.hasAccess && (validEncoding || this.isGS1);
    }

    getContext(rawBarcode) {
        let parsedBarcode = false;
        try {
            parsedBarcode = this.parser.parse_barcode(rawBarcode);
        } catch (err) {
            console.log("Error when parsing barcode:", err.message);
        }

        const context = {
            default_barcode: rawBarcode,
            default_is_storable: true,
            dialog_size: "medium",
            skip_barcode_check: true,
        };

        this.addToContext(parsedBarcode, context);

        return context;
    }

    addToContext(parsedBarcode, context) {
        if (parsedBarcode && this.isGS1) {
            parsedBarcode.forEach((rule) => {
                this.updateContextFromRule(context, rule);
            });
        }
    }

    updateContextFromRule(context, rule) {
        if (rule.type === "product") {
            context.default_barcode = rule.code;
        } else if (rule.type === "lot") {
            context.default_tracking = rule.ai === "21" ? "serial" : "lot";
        }
    }

    async openProductForm(barcodeData) {
        return await this.action.doAction(
            "stock_barcode_barcodelookup.stock_barcodelookup_product_product_action",
            {
                additionalContext: this.getContext(barcodeData.barcode),
                props: {
                    onSave: async (_record) => {
                        this.notification.add(_t("Product created successfully"), {
                            type: "success",
                        });
                        if (barcodeData.callback) {
                            await barcodeData.callback();
                        }
                        return this.action.doAction({ type: "ir.actions.act_window_close" });
                    },
                },
            }
        );
    }
}

registry.category("services").add("stock_barcode_barcodelookup.barcodelookup", {
    dependencies: ["orm", "barcode", "notification", "action"],

    async start(env, services) {
        const barcodeLookupServiceClass = new BarcodeLookupServiceClass(env, services);
        await barcodeLookupServiceClass.setup();
        return barcodeLookupServiceClass;
    },
});
