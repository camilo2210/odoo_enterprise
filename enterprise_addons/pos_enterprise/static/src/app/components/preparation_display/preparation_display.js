import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { useBarcodeReader } from "@point_of_sale/app/hooks/barcode_reader_hook";
import { Category } from "@pos_enterprise/app/components/category/category";
import { Stages } from "@pos_enterprise/app/components/stages/stages";
import { Order } from "@pos_enterprise/app/components/order/order";
import { MainComponentsContainer } from "@web/core/main_components_container";
import { usePrepDisplay } from "@pos_enterprise/app/services/preparation_display_service";
import { Component, onMounted, onPatched, proxy, usePlugin } from "@odoo/owl";
import { init as initDebugFormatters } from "@point_of_sale/app/utils/debug-formatter";
import { cookie } from "@web/core/browser/cookie";
import { location } from "@web/core/browser/browser";
import { DebugModePlugin } from "@web/core/debug_mode_plugin";

export class PrepDisplay extends Component {
    static components = { Category, Stages, Order, MainComponentsContainer };
    static template = `pos_enterprise.PrepDisplay`;

    debugMode = usePlugin(DebugModePlugin);

    setup() {
        this.prepDisplay = usePrepDisplay();
        this.barcodeReader = useService("barcode_reader");
        this.displayName = odoo.preparation_display.name;
        this.showSidebar = true;
        this.onNextPatch = new Set();
        this.state = proxy({
            isMenuOpened: false,
            zoom: 1,
        });
        onPatched(() => {
            for (const cb of this.onNextPatch) {
                cb();
            }
            localStorage.setItem("pdis-zoom", this.state.zoom);
        });

        onMounted(() => {
            this.state.zoom = parseFloat(localStorage.getItem("pdis-zoom")) || 1;
        });

        if (this.debugMode.isActive()) {
            initDebugFormatters();
        }
        useBarcodeReader({
            product: this._barcodeProductAction.bind(this),
        });
    }
    get preparationTheme() {
        return cookie.get("prep_theme") || "light";
    }
    toggleTheme() {
        cookie.set("prep_theme", this.preparationTheme === "dark" ? "light" : "dark");
        location.reload();
    }
    get filterSelected() {
        return (
            this.prepDisplay.selectedCategoryIds.size +
            this.prepDisplay.selectedProductIds.size +
            this.prepDisplay.selectedTimeIds.size +
            this.prepDisplay.selectedPresetIds.size
        );
    }
    get selectedStage() {
        return this.prepDisplay.data.models["pos.prep.stage"].get(this.prepDisplay.selectedStageId);
    }
    changeZoom(value) {
        const currentZoom = parseFloat(this.state.zoom);
        let val = currentZoom + parseFloat(value);
        val = val > 2 ? 2 : val;
        val = val < 0.5 ? 0.5 : val;
        this.state.zoom = val;
    }
    archiveAllVisibleOrders() {
        const lastStageVisibleOrderLines = this.prepDisplay.data.models["pos.prep.line"]
            .getAll()
            .filter((pl) => pl.stage_id === this.prepDisplay.lastStage);

        this.prepDisplay.doneOrders(lastStageVisibleOrderLines);
    }
    resetFilter() {
        this.prepDisplay.selectedCategoryIds = new Set();
        this.prepDisplay.selectedProductIds = new Set();
        this.prepDisplay.selectedTimeIds = new Set();
        this.prepDisplay.selectedPresetIds = new Set();
        this.prepDisplay.saveFilterToLocalStorage();
    }
    toggleCategoryFilter() {
        this.prepDisplay.showCategoryFilter = !this.prepDisplay.showCategoryFilter;
        this.prepDisplay.computeOrderCounts();
    }
    recallLastChange() {
        if (!this.isHistoryEmpty()) {
            this.prepDisplay.changeStateStage(this.selectedStage.recallHistory.pop(), -1, 0);
        } else {
            this.selectedStage.recallHistory.length = 0;
        }
    }
    isHistoryEmpty() {
        const lastElement =
            this.selectedStage.recallHistory[this.selectedStage.recallHistory.length - 1];

        if (lastElement?.some((pl) => pl?.computeDuration() < 10)) {
            return false;
        }
        return true;
    }
    isBurgerMenuClosed() {
        return !this.state.isMenuOpened;
    }
    closeMenu() {
        this.state.isMenuOpened = false;
    }
    openMenu() {
        this.state.isMenuOpened = true;
    }
    get presets() {
        return this.prepDisplay.data.models["pos.preset"].getAll();
    }
    async _barcodeProductAction(code) {
        const prepLines = this.prepDisplay.data.models["pos.prep.line"].filter((line) =>
            (line.associated_barcodes || []).includes(code.code)
        );
        if (!prepLines.length) {
            return this.prepDisplay.notification.add(_t("No order found for the scanned barcode."));
        }
        // Group lines by their current stage so each group advances independently. This prevents split orders from moving all
        // lines to the same next stage. no combo parents will be here as they don't have specific stage and aren't associated to any barcode.
        const prepLinesByStage = Object.values(
            Object.groupBy(
                prepLines.filter((line) => line.stage_id.id !== this.prepDisplay.lastStage.id), // remove lines that are already in last stage
                (line) => line.stage_id.id
            )
        );
        for (const prepLines of prepLinesByStage) {
            const strickedLines = prepLines.filter((l) => !l.todo);
            await this.prepDisplay.changeStateStageAnimation(
                { prepOrder: prepLines[0].prep_order_id, prepLines },
                strickedLines.length ? strickedLines : prepLines
            );
            this.prepDisplay.notification.add(
                _t(
                    "Order moved from %s to %s.",
                    prepLines[0].stage_id.name,
                    this.prepDisplay.orderNextStage(prepLines[0].stage_id.id)?.name
                ),
                { type: "success" }
            );
        }
    }
}
