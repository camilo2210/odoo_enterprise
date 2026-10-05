import { proxy, usePlugin } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { PosDataPlugin } from "@point_of_sale/app/plugins/pos_data_plugin";
import { PosTicketPrinterPlugin } from "@point_of_sale/app/plugins/pos_ticket_printer_plugin";
import { getOnNotified } from "@point_of_sale/utils";
import { useService } from "@web/core/utils/hooks";
import { redirect } from "@web/core/utils/urls";
import { session } from "@web/session";
import { user } from "@web/core/user";
import { WithLazyGetterTrap } from "@point_of_sale/lazy_getter";
import { debounce } from "@web/core/utils/timing";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { EpsonPrinter } from "@point_of_sale/app/utils/printer/epson_printer";

const { DateTime } = luxon;

export class PrepDisplay extends WithLazyGetterTrap {
    static DEPENDENCIES = ["orm", "bus_service", "notification", "dialog"];

    constructor() {
        super(...arguments);
        this.ready = this.setup(...arguments).then(() => this);
    }
    async setup({ env, deps: { bus_service, notification, orm, dialog } }) {
        this.data = usePlugin(PosDataPlugin);
        this.ticketPrinter = usePlugin(PosTicketPrinterPlugin);
        this.ticketPrinter.init(env);

        this.id = odoo.preparation_display.id;
        this.env = env;
        this.orm = orm;
        this.bus = bus_service;
        this.notification = notification;
        this.dialog = dialog;
        this.sound = this.env.services["mail.sound_effects"];

        this.selectedStageId = this.data.models["pos.prep.stage"].getFirst().id;
        this.selectedCategoryIds = new Set();
        this.selectedProductIds = new Set();
        this.selectedPresetIds = new Set();
        this.selectedTimeIds = new Set();
        this.showCategoryFilter = false;
        this.posHasProducts = await this.loadPosHasProducts();
        this.loadingProducts = false;
        this.ringTheBell = debounce(() => {
            this.sound.play("notification");
        }, 1000);

        this.restoreFilterFromLocalStorage();
        this.getPreparationDisplayOrder(null);

        this.orderCountPresets = {};
        this.orderDays = {};
        this.computeOrderCounts();

        this.onNotified = getOnNotified(this.bus, odoo.preparation_display.access_token);
        this.onNotified("LOAD_ORDERS", async (data) => {
            await this.getPreparationDisplayOrder(data.orderId);

            const orderToDisplay = this.data.models["pos.prep.line"].filter(
                (line) => line.stage_id && line.prep_order_id.pos_order_id.id === data.orderId
            );
            const minDuration = Math.min(...orderToDisplay.map((line) => line.timeToShow));

            if (data.sound) {
                if (minDuration) {
                    setTimeout(() => {
                        this.ringTheBell();
                    }, minDuration);
                } else {
                    this.ringTheBell();
                }
            }
            if (data.notification) {
                this.notification.add(data.notification);
            }

            // Auto-print if the latest preparation order starts in the configured stage.
            if (this.prepDisplay.auto_print_stage_id && data.orderId) {
                const [prepOrder] = this.data.models["pos.prep.order"].filter(
                    (order) => order.pos_order_id.id === data.orderId
                );
                const prepLines = prepOrder.prep_line_ids;
                // Use the last line since the first one can be a combo parent which don't have a stage as they are displayed with the child lines.
                if (prepLines.at(-1).stage_id?.id === this.prepDisplay.auto_print_stage_id.id) {
                    await this.printPreparationTicket({ prepOrder, prepLines });
                }
            }
            this.computeOrderCounts();
        });
        this.onNotified("CHANGE_STATE_STATUS", (lineStatus) => {
            for (const status of lineStatus) {
                const line = this.data.models["pos.prep.line"].get(status.id);
                if (!line) {
                    continue;
                }
                line.todo = status.todo;
                if (line.stage_id.id === line.raw.last_stage_id && line.todo === false) {
                    this.filterHistory(line);
                }
            }
            this.computeOrderCounts();
        });
        this.onNotified("POS_ORDER_DELETED", (data) =>
            this.removeOrdersByPosOrderIds(data.pos_order_ids)
        );
        this.bus.addEventListener("BUS:RECONNECT", () => {
            this.ringTheBell();
            this.getPreparationDisplayOrder(null);
        });
        this.prepPrinters = this.prepDisplay?.printer_ids || [];
        this.stageChangedOrderIds = [];
        if (this.prepPrinters.length) {
            this.prepPrinters.forEach((printer) => {
                printer._instance = new EpsonPrinter({ printer });
            });
            this.onNotified("STATE_BARCODE_UPDATE", (data) => {
                const [stateId, associatedBarcodes] = Object.entries(data)[0];
                const prepLine = this.data.models["pos.prep.line"].get(stateId);
                if (prepLine) {
                    prepLine.update({
                        associated_barcodes: associatedBarcodes,
                    });
                }
            });
        }
    }
    get prepDisplay() {
        return this.data.models["pos.prep.display"].get(this.id);
    }
    async changeStateStageAnimation(selectedTicket, prepLines) {
        if (prepLines.length === selectedTicket.prepLines.length) {
            this.stageChangedOrderIds.push(selectedTicket.prepOrder.id);
            setTimeout(async () => {
                this.lastStageChange = await this.changeStateStage(prepLines, 1);
                this.clearChangeTimeout(selectedTicket.prepOrder.id);
            }, 250);
        } else {
            this.lastStageChange = await this.changeStateStage(prepLines, 1);
        }
    }

    clearChangeTimeout(prepOrderId) {
        this.stageChangedOrderIds = this.stageChangedOrderIds.filter(
            (orderId) => orderId !== prepOrderId
        );
    }

    async printPreparationTicket(selectedTicket) {
        let ticketPrinted = false;
        for (const printer of this.prepPrinters) {
            const printerCategoryIds = new Set(
                printer.product_categories_ids.map((category) => category.id)
            );
            const printerLines = selectedTicket.prepLines.filter((line) =>
                line.categories.some((category) => printerCategoryIds.has(category.id))
            );
            // Nothing to print for this printer.
            if (!printerLines.length) {
                continue;
            }
            await this.printReceipt(printer, printerLines);
            ticketPrinted = true;
        }

        // No ticket was printed. Fallback to force-print the complete ticket..
        if (!ticketPrinted) {
            await this.printReceipt(this.prepPrinters[0], selectedTicket.prepLines);
        }
    }

    async printReceipt(printer, prepLines) {
        const prepBarcode = this.prepDisplay.use_barcode
            ? Math.floor(10000 + Math.random() * 90000).toString()
            : "";

        const printerLines = [];
        for (const line of prepLines) {
            // Combo parent lines aren't included in prepLines, so include them explicitly and keep each parent before its child lines.
            const parent = line.combo_parent_id;
            if (parent && !printerLines.some((l) => l.id === parent.id)) {
                printerLines.push(parent);
            }
            printerLines.push(line);
        }

        await this.ticketPrinter.printOrderChanges({
            order: prepLines[0].prep_order_id.pos_order_id,
            opts: {
                prepBarcode,
                prepOrderLines: printerLines,
                template: "pos_enterprise.pos_order_change_receipt",
                forcePrint: true, // No category filtering needed here; print the provided lines.
            },
            printers: [printer],
        });

        if (prepBarcode) {
            await this.assignBarcode(prepBarcode, prepLines);
        }
    }

    async assignBarcode(prepBarcode, prepLines) {
        // Keep a mapping between the generated barcode and the preparation lines
        // included in the printed ticket so that only those lines are updated when scanned.
        for (const line of prepLines) {
            const associatedBarcodes = [...(line.associated_barcodes || []), prepBarcode];
            line.update({ associated_barcodes: associatedBarcodes });
            // Synchronize to all devices
            await this.data.call("pos.prep.line", "update_associated_barcodes", [
                [line.id],
                associatedBarcodes,
                this.id,
            ]);
        }
    }

    get lastStage() {
        return this.data.models["pos.prep.stage"].getAll()[
            this.data.models["pos.prep.stage"].getAll().length - 1
        ];
    }
    get categories() {
        return this.data.models["pos.category"].getAll();
    }
    get activeLines() {
        return this.data.models["pos.prep.line"].getAll().filter((line) => line.stage_id);
    }
    removeOrdersByPosOrderIds(posOrderIds = []) {
        // prep lines cascade from prep orders via the cascade delete models config.
        if (!posOrderIds.length) {
            return;
        }
        const prepOrders = this.data.models["pos.prep.order"].filter(({ pos_order_id }) =>
            posOrderIds.includes(pos_order_id.id)
        );
        prepOrders.forEach((order) => this.data.localDeleteCascade(order));
    }
    filterHistory(line) {
        const previousStage = this.orderNextStage(line.stage_id.id, -1);
        if (!previousStage) {
            return;
        }
        previousStage.recallHistory = previousStage.recallHistory.map(
            (elem) => (elem = elem.filter((historyLine) => historyLine.id !== line.id))
        );
    }
    selectStage(stageId) {
        this.selectedStageId = stageId;
        this.computeOrderCounts();
    }
    saveFilterToLocalStorage() {
        const localStorageName = `preparation_display_${this.id}.db_${session.db}.user_${user.userId}`;
        localStorage.setItem(
            localStorageName,
            JSON.stringify({
                products: Array.from(this.selectedProductIds),
                categories: Array.from(this.selectedCategoryIds),
                times: Array.from(this.selectedTimeIds),
                presets: Array.from(this.selectedPresetIds),
            })
        );
    }
    restoreFilterFromLocalStorage() {
        const localStorageName = `preparation_display_${this.id}.db_${session.db}.user_${user.userId}`;
        const localStorageData = JSON.parse(localStorage.getItem(localStorageName));

        if (localStorageData) {
            this.selectedCategoryIds = new Set(localStorageData.categories);
            this.selectedProductIds = new Set(localStorageData.products);
            this.selectedTimeIds = new Set(localStorageData.times);
            this.selectedPresetIds = new Set(localStorageData.presets);
        }
    }
    toggleSelection(id, selectedIdsSet, relatedIds, relatedIdsSet) {
        if (selectedIdsSet.has(id)) {
            selectedIdsSet.delete(id);
        } else {
            selectedIdsSet.add(id);
            relatedIds.forEach((relatedId) => relatedIdsSet.delete(relatedId));
        }

        this.saveFilterToLocalStorage();
    }
    toggleCategory(category) {
        const categoryId = category.id;
        const categoryProductIds = this.data.models["product.product"]
            .filter((p) => p.pos_categ_ids.map((categ) => categ.id).includes(categoryId))
            .map((p) => p.id);

        this.toggleSelection(
            categoryId,
            this.selectedCategoryIds,
            categoryProductIds,
            this.selectedProductIds
        );
    }
    toggleProduct(product) {
        const productId = product.id;
        const categoryIds = product.categoryIds;

        this.toggleSelection(
            productId,
            this.selectedProductIds,
            categoryIds,
            this.selectedCategoryIds
        );
    }
    toggleTime(time) {
        this.selectedTimeIds.has(time)
            ? this.selectedTimeIds.delete(time)
            : this.selectedTimeIds.add(time);
        this.saveFilterToLocalStorage();
    }
    togglePreset(presetId) {
        this.selectedPresetIds.has(presetId)
            ? this.selectedPresetIds.delete(presetId)
            : this.selectedPresetIds.add(presetId);
        this.saveFilterToLocalStorage();
    }
    checkStateVisibility(line) {
        const selectedCategoryIds = this.selectedCategoryIds;
        const selectedProductIds = this.selectedProductIds;
        const selectedPresetIds = this.selectedPresetIds;
        const selectedTimeIds = this.selectedTimeIds;
        const now = DateTime.now().startOf("day");
        const timeMap = {
            today: now,
            tomorrow: now.plus({ days: 1 }),
            nextDays: now.plus({ days: 2 }),
        };
        let timeCheck = true;

        if (selectedTimeIds.size) {
            const orderDate = line.prep_order_id.pos_order_id.preset_time;
            if (!orderDate) {
                timeCheck = selectedTimeIds.has("today");
            } else {
                timeCheck =
                    (selectedTimeIds.has("today") && orderDate.hasSame(timeMap.today, "day")) ||
                    (selectedTimeIds.has("tomorrow") &&
                        orderDate.hasSame(timeMap.tomorrow, "day")) ||
                    (selectedTimeIds.has("next_days") && orderDate >= timeMap.nextDays);
            }
        }

        const categoryMatch =
            selectedCategoryIds.size === 0 ||
            line.categories.some((category) => selectedCategoryIds.has(category.id));
        const productMatch =
            selectedProductIds.size === 0 || selectedProductIds.has(line.product.id);
        const presetId = line.prep_order_id.pos_order_id.preset_id;
        const presetMatch =
            selectedPresetIds.size === 0 || Boolean(presetId && selectedPresetIds.has(presetId.id));
        const notDoneOrLastStage = line.todo || line.stage_id.id !== line.raw.last_stage_id;

        return (
            notDoneOrLastStage &&
            categoryMatch &&
            productMatch &&
            presetMatch &&
            (timeCheck || (line.timeToShow === 0 && selectedTimeIds.has("now")))
        );
    }
    orderNextStage(stageId, direction = 1) {
        if (stageId === this.lastStage.id && direction === 1) {
            return this.data.models["pos.prep.stage"].getFirst();
        }

        const stages = this.data.models["pos.prep.stage"].getAll();
        const currentStagesIdx = stages.findIndex((stage) => stage.id === stageId);

        return stages[currentStagesIdx + direction] ?? false;
    }
    computeOrderDays() {
        const orderDays = { now: 0, today: 0, tomorrow: 0, next_days: 0 };
        const now = DateTime.now().startOf("day");
        const tomorrow = now.plus({ days: 1 });
        const nextDays = now.plus({ days: 2 });
        const countedOrders = new Set();

        this.activeLines.forEach((line) => {
            const prepOrder = line.prep_order_id;
            if (
                (!this.selectedStageId || line.stage_id.id === this.selectedStageId) &&
                !countedOrders.has(prepOrder.id) &&
                !line.isStageDone()
            ) {
                countedOrders.add(prepOrder.id);
                const orderDate = prepOrder.pos_order_id.preset_time;
                if (!orderDate || orderDate.hasSame(now, "day")) {
                    orderDays.today++;
                }
                if (orderDate?.hasSame(tomorrow, "day")) {
                    orderDays.tomorrow++;
                }
                if (orderDate && orderDate >= nextDays) {
                    orderDays.next_days++;
                }
                if (!orderDate || line.timeToShow === 0) {
                    orderDays.now++;
                }
            }
        });
        orderDays[0] = countedOrders.size;
        this.orderDays = orderDays;
    }
    computeOrderCountPresets() {
        const allLines = this.activeLines;
        const orderPresets = {};
        this.data.models["pos.preset"].getAll().forEach((preset) => {
            orderPresets[preset.id] = 0;
        });
        const countedOrders = new Set();
        allLines.forEach((line) => {
            const prepOrder = line.prep_order_id;
            const presetId = prepOrder.pos_order_id.preset_id;
            if (
                (!this.selectedStageId || line.stage_id.id === this.selectedStageId) &&
                presetId &&
                !countedOrders.has(prepOrder.id) &&
                !line.isStageDone()
            ) {
                countedOrders.add(prepOrder.id);
                orderPresets[presetId.id] += 1;
            }
        });
        orderPresets[0] = countedOrders.size;
        this.orderCountPresets = orderPresets;
    }
    computeOrderCounts() {
        if (this.showCategoryFilter) {
            this.computeOrderDays();
            this.computeOrderCountPresets();
        }
    }
    getFilteredOrdersKey(line) {
        return line.prep_order_id.id + "-" + line.stage_id.id;
    }
    getOrderlineInfo(line) {
        return {
            prepOrder: line.prep_order_id,
            stage: line.stage_id,
            prepLines: [],
        };
    }
    get filteredOrders() {
        const ordersToDisplay = new Map();
        this.activeLines.forEach((line) => {
            if (
                this.checkStateVisibility(line) &&
                (!this.selectedStageId || line.stage_id.id === this.selectedStageId)
            ) {
                const key = this.getFilteredOrdersKey(line);
                if (!ordersToDisplay.has(key)) {
                    ordersToDisplay.set(key, this.getOrderlineInfo(line));
                }
                ordersToDisplay.get(key).prepLines.push(line);
            }
        });

        return Array.from(ordersToDisplay.values()).sort((a, b) => {
            const stageA = a.stage;
            const stageB = b.stage;
            const stageDiff = stageA.sequence - stageB.sequence || stageA.id - stageB.id; // sort by stage

            if (stageDiff) {
                return stageDiff;
            }
            // within the stage, keep the default order unless the preparation line is done then show most recent first.
            let difference;
            const aWriteDate = Math.max(...a.prepLines.map((line) => line.last_stage_change.ts));
            const bWriteDate = Math.max(...b.prepLines.map((line) => line.last_stage_change.ts));
            if (stageA.id === this.lastStage.id) {
                difference = bWriteDate - aWriteDate;
            } else {
                difference =
                    (a.prepOrder.pos_order_id.preset_time || aWriteDate) -
                    (b.prepOrder.pos_order_id.preset_time || bWriteDate);
            }

            return difference;
        });
    }
    async syncStateStatus(lines) {
        const lineStatus = {};
        const lineIds = [];

        for (const line of lines) {
            lineIds.push(line.id);
            lineStatus[line.id] = line.todo;
        }
        await this.orm.call("pos.prep.line", "change_state_status", [lineIds, lineStatus], {});
    }
    async doneOrders(lines) {
        lines.forEach((line) => (line.todo = false));
        this.syncStateStatus(lines);
    }
    async changeStateStage(lines, direction = 1) {
        const currentStage = lines[0].stage_id;
        const lineIds = lines.map((line) => line.id);

        await this.orm.call("pos.prep.line", "change_prep_line_stage", [lineIds, this.id], {
            direction,
        });
        if (direction === 1) {
            currentStage.recallHistory.push(lines);
        }
        if (this.prepPrinters.length && this.prepDisplay.auto_print_stage_id && direction > 0) {
            // Automatically print KOT for all moved orders.
            const nextStage = this.orderNextStage(currentStage.id, direction);
            if (nextStage.id === this.prepDisplay.auto_print_stage_id?.id) {
                const prepOrders = new Map();
                // Group moved preparation lines by preparation order.
                for (const line of lines) {
                    const order = line.prep_order_id;
                    if (!prepOrders.has(order.id)) {
                        prepOrders.set(order.id, {
                            prepOrder: order,
                            prepLines: [],
                        });
                    }
                    prepOrders.get(order.id).prepLines.push(line);
                }

                for (const { prepOrder, prepLines } of prepOrders.values()) {
                    await this.printPreparationTicket({ prepOrder, prepLines });
                }
            }
        }
    }
    clearAllOrders() {
        const message =
            this.filteredOrders[0].stage.id === this.lastStage.id
                ? _t(
                      "All orders are in the last stage. This action will mark all orders as Done. Would you like to continue?"
                  )
                : _t(
                      "Clearing all orders will move all the orders of the current stage to the next one. Would you like to continue?"
                  );
        this.dialog.add(ConfirmationDialog, {
            title: _t("Warning"),
            body: message,
            confirmLabel: _t("Continue"),
            cancelLabel: _t("Discard"),
            confirm: async () => await this.moveAllOrdersToNextStage(),
            cancel: () => {},
        });
    }
    async moveAllOrdersToNextStage() {
        const lines = this.filteredOrders.flatMap((order) => order.prepLines);
        this.filteredOrders[0].stage.id === this.lastStage.id
            ? await this.doneOrders(lines)
            : await this.changeStateStage(lines);
    }
    async resetOrders() {
        this.data.models["pos.prep.line"].deleteMany(this.data.models["pos.prep.line"].getAll());
        const stages = this.data.models["pos.prep.stage"].getAll();
        stages.map((stage) => (stage.recallHistory = []));
        await this.data.call("pos.prep.display", "reset", [[this.id]]);
    }
    async loadPosHasProducts() {
        return await this.orm.call("pos.prep.display", "pos_has_valid_product", [], {});
    }
    async loadScenarioRestaurantData() {
        this.loadingProducts = true;
        try {
            await this.orm.call("pos.config", "load_onboarding_restaurant_scenario");
        } finally {
            window.location.reload();
        }
    }
    async getPreparationDisplayOrder() {
        const orders = await this.orm.call(
            "pos.prep.display",
            "get_preparation_display_orders",
            [this.id],
            {}
        );

        const serverLineIds = new Set((orders["pos.prep.line"] || []).map((r) => r.id));

        this.data.models["pos.prep.line"]
            .filter((line) => !serverLineIds.has(line.id))
            .forEach((line) => line.delete());
        const missingRecords = await this.data.missingRecursive(orders);
        this.data.models.loadConnectedData(missingRecords, [], { delaySetup: true });
        this.computeOrderCounts();
    }
    exit() {
        redirect("/odoo/action-pos_enterprise.action_preparation_display");
    }
    get displayPresetsFilter() {
        return this.data.models["pos.config"].some((config) => config.use_presets);
    }
}

export const preparationDisplayService = {
    dependencies: PrepDisplay.DEPENDENCIES,
    async start(env, services) {
        return new PrepDisplay({ traps: {}, env, deps: services }).ready;
    },
};

registry.category("services").add("preparation_display", preparationDisplayService);

/**
 * @returns {PrepDisplay}
 */
export function usePrepDisplay() {
    return proxy(useService("preparation_display"));
}
