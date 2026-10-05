import { useSubEnv } from "@web/owl2/utils";
import { ManualBarcodeScanner } from "@barcodes/components/manual_barcode";
import { Mutex } from "@web/core/utils/concurrency";
import { useBus, useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";

import { FSMProductCatalogKanbanController } from "@planning_field_service_sale_timesheet/views/product_catalog/kanban_controller";

patch(FSMProductCatalogKanbanController.prototype, {
    setup() {
        super.setup();
        this.notification = useService("notification");

        this.barcodeService = useService("barcode");
        this.scanMutex = new Mutex();
        useBus(this.barcodeService.bus, "barcode_scanned", (ev) =>
            this.scanMutex.exec(() => this._onBarcodeScanned(ev.detail.barcode))
        );

        useSubEnv({
            config: {
                ...this.env.config,
                disableSearchBarAutofocus: true,
            },
        });
    },

    onScanClick() {
        this.dialog.add(ManualBarcodeScanner, {
            facingMode: "environment",
            onResult: (barcode) => this.barcodeService.bus.trigger("barcode_scanned", { barcode }),
            onError: () => {},
        });
    },

    async _onBarcodeScanned(barcode) {
        if (!barcode || barcode.startsWith("OBT") || barcode.startsWith("OCD")) {
            return;
        }

        const interventionId = this.interventionId || this.props.context.active_id;
        const sectionId = this.env.searchModel.selectedSectionId;
        const res = await this.orm.call(
            "planning.slot",
            "action_fsm_add_product_from_barcode",
            [[interventionId], barcode],
            {
                context: {
                    ...this.props.context,
                    section_id: sectionId,
                },
            }
        );

        if (res.action) {
            await this.actionService.doAction(res.action, {
                onClose: () => {
                    this._onTrackingWizardClosed(
                        res.product_id,
                        res.quantity,
                        interventionId,
                        sectionId
                    );
                },
            });
            return;
        }

        this.notification.add(res.message, { type: res.type });
        if (res.type !== "success") {
            return;
        }

        if ("vibrate" in window.navigator) {
            window.navigator.vibrate(100);
        }
        const record = this._catalogRecord(res.product_id);
        if (record) {
            record.productCatalogData.quantity = res.quantity;
            record.productCatalogData.subtotal =
                (record.productCatalogData.subtotal ?? 0) + res.subtotal_delta;
        } else {
            await this.model.load();
        }
        if (res.subtotal_delta) {
            this.env.searchModel.trigger("section-subtotal-change", {
                sectionId,
                subtotalDelta: res.subtotal_delta,
            });
        }
    },

    async _onTrackingWizardClosed(productId, previousQuantity, interventionId, sectionId) {
        const { message, type, quantity } = await this.orm.call(
            "planning.slot",
            "get_fsm_barcode_notification",
            [[interventionId], productId],
            { context: { ...this.props.context, section_id: sectionId } }
        );
        if (quantity === previousQuantity) {
            return;
        }
        const record = this._catalogRecord(productId);
        if (record) {
            record.productCatalogData.quantity = quantity;
        }
        this.notification.add(message, { type });
    },

    _catalogRecord(productId) {
        return this.model.root.records?.find((r) => r.resId === productId);
    },
});
