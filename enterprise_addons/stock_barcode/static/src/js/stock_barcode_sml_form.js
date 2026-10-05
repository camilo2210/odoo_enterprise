import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";
import { FormRenderer } from "@web/views/form/form_renderer";
import { browser } from "@web/core/browser/browser";
import { getViewportDimensions, useViewportChange } from "@web/core/utils/dvu";
import { onWillStart, onWillUnmount, useOnChange } from "@odoo/owl";
import { SuggestBatchDialog } from "../components/suggest_batch_dialog";

export class StockBarcodeSmlFormController extends FormController {
    setup() {
        super.setup();
        this.actionService = useService("action");
        this.dialogService = useService("dialog");
        this.orm = useService("orm");
        onWillStart(async () => {
            this.locationsEnabled = await user.hasGroup("stock.group_stock_multi_locations");
            this.batchEnabled = await user.hasGroup("stock.group_stock_picking_batch");
        });
    }

    mustCheckQuantityAvailableInLocation(data) {
        return (
            data.product_id &&
            this.locationsEnabled &&
            data.qty_done > 0 &&
            data.picking_code &&
            data.picking_code !== "incoming" &&
            !this.model.root.context?.newByProduct
        );
    }

    displayName() {
        return super.displayName() || this.props.context.display_name;
    }

    /**
     * @override
     */
    async beforeExecuteActionButton(clickParams) {
        let proceed = true;
        if (clickParams.special && clickParams.special === "save") {
            const { data } = this.model.root;
            if (!data.id && this.props.context.candidatePickingsToBatch?.length) {
                // Check if added product is not in the current receipt and is
                // in another receipt which is sharing same vendor.
                const { candidatePickingsToBatch } = this.props.context;
                const product = data.product_id;
                const candidates = candidatePickingsToBatch.filter((picking) =>
                    picking.product_ids.includes(product.id)
                );
                if (candidates.length) {
                    // If there is at least on good candidate, ask the user if they want to
                    // batch this operation with another one which waits the scanned product.
                    const body = _t(
                        "%(product)s was not expected for this receipt but can be found in other waiting receipts ",
                        { product: product.display_name }
                    );
                    const title = _t("Batch Receipts from %(partner)s?", {
                        partner: candidates[0].partner_name,
                    });
                    proceed = await new Promise((resolve) => {
                        this.dialogService.add(SuggestBatchDialog, {
                            body,
                            candidates,
                            product,
                            title,
                            addProduct: () => resolve(true),
                            cancel: () => resolve(false),
                            close: () => resolve(false),
                            confirm: async (selectedPicking) => {
                                const kwargs = { product_id: product.id };
                                const batchAction = await this.orm.call(
                                    "stock.picking",
                                    "action_batch_pickings_from_barcode",
                                    [data.picking_id.id, [selectedPicking.id]],
                                    kwargs
                                );
                                resolve(false); // Don't add the move line in the current picking.
                                return this.actionService.doAction(batchAction, {
                                    stackPosition: "replaceCurrentAction",
                                });
                            },
                        });
                    });
                }
            }
            if (this.mustCheckQuantityAvailableInLocation(data)) {
                const context = {
                    location: data.location_id.id,
                    lot_id: data.lot_id ? data.lot_id.id : false,
                    package_id: data.package_id ? data.package_id.id : false,
                    owner_id: data.owner_id ? data.owner_id.id : false,
                    strict: true,
                    active_test: false,
                };
                const [{ is_storable, qty_available }] = await this.orm.searchRead(
                    "product.product",
                    [["id", "=", data.product_id.id]],
                    ["is_storable", "qty_available"],
                    { context, limit: 1 }
                );
                if (is_storable && !qty_available) {
                    proceed = await new Promise((resolve) => {
                        this.dialogService.add(ConfirmationDialog, {
                            body: _t(
                                "Oops! It seems that this product is not located in %(location)s.\nDo you confirm you picked from there?",
                                { location: data.location_id.display_name }
                            ),
                            confirmLabel: _t("Confirm"),
                            confirm: () => resolve(true),
                            cancel: () => resolve(false),
                        });
                    });
                }
            }
        }
        return proceed && super.beforeExecuteActionButton(...arguments);
    }
}

export class StockBarcodeFormRenderer extends FormRenderer {
    setup() {
        super.setup();

        // Focus the field marked with default_focus="1" on mount, for both new and
        // existing records and regardless of touch device (overrides the isNew gate
        // and hasTouch guard in the standard FormRenderer).
        const { autofocusFieldIds } = this.props.archInfo;
        if (autofocusFieldIds && autofocusFieldIds.length) {
            useOnChange(
                () => [this.rootRef()],
                (rootEl) => {
                    if (!rootEl) {
                        return;
                    }
                    for (const id of autofocusFieldIds) {
                        const el = rootEl.querySelector(`#${id}`);
                        if (el) {
                            el.focus();
                            break;
                        }
                    }
                }
            );
        }

        useViewportChange(() => {
            const rootEl = this.rootRef();
            const footer = rootEl?.querySelector(".fixed-bottom");
            if (!footer) {
                return;
            }
            const viewportHeight = getViewportDimensions().height;
            const keyboardHeight = Math.max(0, browser.innerHeight - viewportHeight);
            const container = rootEl.closest(".o_web_client");
            if (container) {
                container.style.height = keyboardHeight ? `${viewportHeight}px` : "";
                container.style.overflow = keyboardHeight ? "hidden" : "";
            }

            const offsetTop = browser.visualViewport?.offsetTop || 0;
            footer.style.transform = keyboardHeight
                ? `translateY(${offsetTop - keyboardHeight}px)`
                : "";
        });

        onWillUnmount(() => {
            const container = this.rootRef()?.closest(".o_web_client");
            if (container) {
                container.style.height = "";
                container.style.overflow = "";
            }
        });
    }
}

export const stockBarcodeSmlFormView = {
    ...formView,
    Controller: StockBarcodeSmlFormController,
    Renderer: StockBarcodeFormRenderer,
};

registry.category("views").add("stock_barcode_sml_form", stockBarcodeSmlFormView);
