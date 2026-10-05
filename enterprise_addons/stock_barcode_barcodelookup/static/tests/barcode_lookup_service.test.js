import { describe, expect, test } from "@odoo/hoot";
import { EventBus } from "@odoo/owl";
import { user } from "@web/core/user";
import {
    defineModels,
    fields,
    getService,
    getMockEnv,
    makeTestApp,
    models,
    onRpc,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";

import { BarcodeParser } from "@barcodes/js/barcode_parser";

import { BarcodeLookupServiceClass } from "../src/barcodelookup_service";

class ResCompany extends models.Model {
    _name = "res.company";
    nomenclature_id = fields.Many2one({ relation: "barcode.nomenclature" });
}

class BarcodeNomenclature extends models.Model {
    _name = "barcode.nomenclature";
}

defineModels({ ResCompany, BarcodeNomenclature });

describe("BarcodeLookupServiceClass", () => {
    async function setupService({ hasAccess = true, nomenclatureData = {} }) {
        patchWithCleanup(user, {
            activeCompany: { id: 101 },
            hasGroup: async () => hasAccess,
        });

        const realFetch = BarcodeParser.fetchNomenclature;
        BarcodeParser.fetchNomenclature = async () => nomenclatureData;

        const realEncodingCheck = BarcodeParser.prototype.check_encoding;
        const changeCheckEncoding = (value = true) => {
            BarcodeParser.prototype.check_encoding = (_barcode, _encoding) => {
                expect.step("barcode_check_encoding_call");
                return value;
            };
        };

        const realParseBarcode = BarcodeParser.prototype.parse_barcode;
        const changeParseBarcode = (outputData) => {
            BarcodeParser.prototype.parse_barcode = (_rawBarcode) => {
                expect.step("barcode_parser_call");
                return outputData;
            };
        };

        // Mock orm calls
        onRpc("barcode.nomenclature", "read", () => {
            expect.step("barcode_nomenclature_read");
        });
        onRpc("barcode.rule", "search_read", () => []);
        onRpc("res.company", "search_read", () => [
            { id: 101, nomenclature_id: [42, "Standard Nomenclature"] },
        ]);

        // Mock barcode
        const mockBarcodeBus = new EventBus();

        // Mock notification
        const mockNotification = {
            add: (_content, options) => {
                if (options?.type === "success") {
                    expect.step("product_creation_successful");
                } else {
                    if (options?.buttons) {
                        expect.step("product_creation_notification_added");
                        options?.buttons[0].onClick();
                    } else {
                        expect.step("simple_notification_added");
                    }
                }
                return "notification_id";
            },
        };

        // Mock action
        const mockAction = {
            doAction: async (actionId, params) => {
                if (
                    actionId ===
                    "stock_barcode_barcodelookup.stock_barcodelookup_product_product_action"
                ) {
                    await params.props.onSave(actionId);
                }
                return true;
            },
        };

        await makeTestApp();

        const services = {
            orm: getService("orm"),
            barcode: { bus: mockBarcodeBus },
            notification: mockNotification,
            action: mockAction,
        };

        const barcodeLookupService = new BarcodeLookupServiceClass(getMockEnv(), services);
        await barcodeLookupService.setup();

        // Function to return back to the original state
        const teardown = () => {
            BarcodeParser.fetchNomenclature = realFetch;
            BarcodeParser.prototype.check_encoding = realEncodingCheck;
            BarcodeParser.prototype.parse_barcode = realParseBarcode;
        };

        return {
            barcodeLookupService,
            mockBarcodeBus,
            teardown,
            changeParseBarcode,
            changeCheckEncoding,
        };
    }

    // Test getContext function
    test("getContext: should return the default context because not GS1", async () => {
        const { barcodeLookupService, changeParseBarcode, teardown } = await setupService({
            nomenclatureData: { is_gs1_nomenclature: false },
        });

        changeParseBarcode([{ type: "product", code: "123456789" }]);
        const currContext = barcodeLookupService.getContext("01123456789");

        expect.verifySteps(["barcode_parser_call"]);
        expect(currContext).toEqual({
            default_barcode: "01123456789",
            default_is_storable: true,
            dialog_size: "medium",
            skip_barcode_check: true,
        });

        teardown();
    });

    test("getContext: should change barcode and add serial tracking", async () => {
        const { barcodeLookupService, changeParseBarcode, teardown } = await setupService({
            nomenclatureData: { is_gs1_nomenclature: true },
        });

        changeParseBarcode([
            { type: "product", code: "123456789" },
            { type: "lot", ai: "21" },
        ]);
        const currContext = barcodeLookupService.getContext("01123456789");

        expect.verifySteps(["barcode_parser_call"]);
        expect(currContext).toEqual({
            default_barcode: "123456789",
            default_is_storable: true,
            dialog_size: "medium",
            skip_barcode_check: true,
            default_tracking: "serial",
        });

        teardown();
    });

    test("getContext: should change barcode and add lot tracking", async () => {
        const { barcodeLookupService, changeParseBarcode, teardown } = await setupService({
            nomenclatureData: { is_gs1_nomenclature: true },
        });

        changeParseBarcode([
            { type: "product", code: "123456789" },
            { type: "lot", ai: "10" },
        ]);
        const currContext = barcodeLookupService.getContext("01123456789");

        expect.verifySteps(["barcode_parser_call"]);
        expect(currContext).toEqual({
            default_barcode: "123456789",
            default_is_storable: true,
            dialog_size: "medium",
            skip_barcode_check: true,
            default_tracking: "lot",
        });

        teardown();
    });

    // Test allowProductCreation
    test("allowProductCreation: should return false since it is not an admin", async () => {
        const { barcodeLookupService, changeCheckEncoding, changeParseBarcode, teardown } =
            await setupService({
                nomenclatureData: { is_gs1_nomenclature: true },
                hasAccess: false,
            });

        changeParseBarcode([
            { type: "product", code: "123456789" },
            { type: "lot", ai: "10" },
        ]);
        changeCheckEncoding(true);
        const result = barcodeLookupService.allowProductCreation("01123456789");

        expect(result).toEqual(false);

        teardown();
    });

    test("allowProductCreation: should return false because not gs1 and not valid encoding", async () => {
        const { barcodeLookupService, changeCheckEncoding, changeParseBarcode, teardown } =
            await setupService({
                nomenclatureData: { is_gs1_nomenclature: false },
                hasAccess: true,
            });

        changeParseBarcode([
            { type: "product", code: "123456789" },
            { type: "lot", ai: "10" },
        ]);
        changeCheckEncoding(false);
        const result = barcodeLookupService.allowProductCreation("01123456789");

        expect.verifySteps([
            "barcode_check_encoding_call",
            "barcode_check_encoding_call",
            "barcode_check_encoding_call",
        ]);
        expect(result).toEqual(false);

        teardown();
    });

    test("allowProductCreation: should return true because not gs1 and but valid encoding", async () => {
        const { barcodeLookupService, changeCheckEncoding, changeParseBarcode, teardown } =
            await setupService({
                nomenclatureData: { is_gs1_nomenclature: false },
                hasAccess: true,
            });

        changeParseBarcode([
            { type: "product", code: "123456789" },
            { type: "lot", ai: "10" },
        ]);
        changeCheckEncoding(true);
        const result = barcodeLookupService.allowProductCreation("01123456789");

        expect.verifySteps(["barcode_check_encoding_call"]);
        expect(result).toEqual(true);

        teardown();
    });

    test("allowProductCreation: should return true because gs1", async () => {
        const { barcodeLookupService, changeCheckEncoding, changeParseBarcode, teardown } =
            await setupService({
                nomenclatureData: { is_gs1_nomenclature: true },
                hasAccess: true,
            });

        changeParseBarcode([
            { type: "product", code: "123456789" },
            { type: "lot", ai: "10" },
        ]);
        changeCheckEncoding(false);
        const result = barcodeLookupService.allowProductCreation("01123456789");

        expect.verifySteps([
            "barcode_check_encoding_call",
            "barcode_check_encoding_call",
            "barcode_check_encoding_call",
        ]);
        expect(result).toEqual(true);

        teardown();
    });

    // Test notification displaying
    test("Check that simple notification is displayed", async () => {
        const { mockBarcodeBus, changeCheckEncoding, changeParseBarcode, teardown } =
            await setupService({
                nomenclatureData: { is_gs1_nomenclature: true },
                hasAccess: false,
            });

        changeParseBarcode([
            { type: "product", code: "123456789" },
            { type: "lot", ai: "10" },
        ]);
        changeCheckEncoding(true);
        mockBarcodeBus.trigger("create_product", {
            barcodeData: {
                barcode: "01123456789",
                content: "No product",
            },
        });

        expect.verifySteps(["simple_notification_added"]);

        teardown();
    });

    test("Check that product creation is displayed and invoked", async () => {
        const { mockBarcodeBus, changeCheckEncoding, changeParseBarcode, teardown } =
            await setupService({
                nomenclatureData: { is_gs1_nomenclature: true },
                hasAccess: true,
            });

        changeParseBarcode([
            { type: "product", code: "123456789" },
            { type: "lot", ai: "10" },
        ]);
        changeCheckEncoding(true);
        mockBarcodeBus.trigger("create_product", {
            barcodeData: {
                barcode: "01123456789",
                content: "No product",
                callback: () => {
                    expect.step("callback_called");
                },
            },
        });

        expect.verifySteps([
            "barcode_check_encoding_call",
            "product_creation_notification_added",
            "barcode_parser_call",
            "product_creation_successful",
            "callback_called",
        ]);

        teardown();
    });
});
