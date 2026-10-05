import BarcodePickingModel from "@stock_barcode/models/barcode_picking_model";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { x2ManyCommands } from "@web/core/orm_plugin";
import { deepEqual } from "@web/core/utils/objects";

export default class BarcodeMRPModel extends BarcodePickingModel {
    constructor(params) {
        super(...arguments);
        this.lineModel = "stock.move.line";
        this.showBackOrderDialog = false;
        this.validateMessage = _t("The manufacturing order has been validated");
        this.validateMethod = "button_mark_done";
        this.validateContext = {};
        this.backorderModel = "mrp.production";
        this.actionName = "stock_barcode_mrp.stock_barcode_mo_client_action";
        this.componentLoaded = false;
        this.displayByProduct = false;
    }

    get cancelLabel() {
        return _t("Cancel Manufacturing Order");
    }

    get canScrap() {
        const { state } = this.record;
        return state != "cancel" && state != "draft";
    }

    _cancelNotification() {
        this.notification(_t("The Manufacturing Order has been cancelled"));
    }

    get printButtons() {
        const buttons = [
            {
                name: _t("Print Production Order"),
                class: "o_print_production",
                action: "mrp.action_report_production_order",
            },
            {
                name: _t("Print Finished Product Label (ZPL)"),
                class: "o_print_finished_product_zpl",
                action: "mrp.action_print_finished_product_zpl",
            },
            {
                name: _t("Print Finished Product Label (PDF)"),
                class: "o_print_finsihed_product_pdf",
                action: "mrp.action_print_finished_product_pdf",
            },
        ];
        if (this.groups.group_tracking_lot) {
            buttons.push({
                name: _t("Print Packages"),
                class: "o_print_packages",
                action: "mrp.action_report_mrp_packages",
            });
        }
        return buttons;
    }

    get barcodeInfo() {
        const barcodeInfo = super.barcodeInfo;
        if (this.isCancelled || this.isDone) {
            return {
                class: this.isDone ? "order_already_done" : "order_already_cancelled",
                message: this.isDone
                    ? _t("This order is already done")
                    : _t("This order is cancelled"),
                icon: "warning",
                warning: true,
            };
        }
        if (barcodeInfo.class === "scan_product" && this.record.product_id) {
            return {
                message: _t("Scan a component"),
                class: "scan_component",
                icon: "sell",
            };
        } else if (
            barcodeInfo.class === "scan_validate" &&
            this.record.qty_producing < this.record.product_qty
        ) {
            return {
                message: _t("Scan your final product or more components"),
                class: "scan_final_product",
                icon: "sell",
            };
        } else if (barcodeInfo.class === "scan_validate") {
            barcodeInfo.message = _t("Press 'Produce' or scan another component");
        }
        return barcodeInfo;
    }

    get displayRegisterByProduct() {
        return this.groups.group_mrp_byproducts && this.record.product_id && !this.displayByProduct;
    }

    get displayAllocationButton() {
        return Boolean(this.record?.product_qty);
    }

    get displayValidateButton() {
        return !this.displayByProduct;
    }

    get displayPutInPackButton() {
        return (
            super.displayPutInPackButton &&
            this.record.state !== "done" &&
            this.record.state !== "cancel"
        );
    }

    get moveIds() {
        return this.record.move_raw_ids;
    }

    get useExistingLots() {
        return true;
    }

    get showReservedSns() {
        return this.record.picking_type_id.show_reserved_sns || this.displayByProduct;
    }

    get isComplete() {
        if (
            ["lot", "serial"].includes(this.record.product_id.tracking) &&
            !(this.record.lot_producing_ids.length || this.record.lot_name)
        ) {
            return false;
        }
        return this.record.qty_producing >= this.record.product_qty;
    }

    get highlightValidateButton() {
        return this.canBeValidate && this.isComplete;
    }

    get pageLines() {
        if (this.displayByProduct) {
            return this.currentState.lines.filter((line) => line.byProduct);
        }
        return this.currentState.lines.filter((line) => !line.byProduct);
    }

    get displaySourceLocation() {
        return this.groups.group_stock_multi_locations;
    }

    get canBeValidate() {
        if (!this.config.barcode_validation_full && !this.record.qty_producing) {
            return false;
        }
        return ["confirmed", "progress", "to_close"].includes(this.record.state);
    }

    get canCreateNewLot() {
        const currentLine =
            this.selectedLine && ["lot", "serial"].includes(this.selectedLine.product_id.tracking)
                ? this.selectedLine
                : this.lastScannedLine &&
                  ["lot", "serial"].includes(this.lastScannedLine.product_id.tracking)
                ? this.lastScannedLine
                : this.selectedLine || this.lastScannedLine;
        if (
            currentLine &&
            currentLine.product_id != this.record.product_id &&
            !currentLine.byProduct
        ) {
            return this.record.use_create_components_lots;
        } else {
            return true;
        }
    }

    get scrapContext() {
        const context = {
            ...this._getNewLineDefaultContext(),
            scrapProduct: true,
            default_location_dest_id: this._defaultScrapLocation().id,
            default_quantity: 1.0,
            default_is_scrap: true,
        };
        delete context.default_qty_done;
        if (this.record.state !== "done") {
            context.product_ids = this.pageLines.map((line) => line.product_id.id);
        } else {
            context.product_ids = this.byProductLines
                ? this.byProductLines.map((line) => line.product_id.id)
                : [];
            context.product_ids.push(this.record.product_id.id);
        }
        return context;
    }

    get selectedLine() {
        if (this.record.virtualId === this.selectedLineVirtualId) {
            return this._getFinalProductLine();
        }
        return super.selectedLine;
    }

    get backordersDomain() {
        return [
            ["id", "not in", this.record.backorder_ids],
            [
                "production_group_id.production_ids",
                "=",
                this.record.production_group_id.production_ids,
            ],
            ["state", "=", "confirmed"],
        ];
    }

    get operationSourceLocation() {
        if (this.record) {
            return this.cache.getRecord("stock.location", this.record.location_src_id);
        }
        return false;
    }

    get validateButtonLabel() {
        return _t("Produce");
    }

    get canPutInPack() {
        return this.resId || super.canPutInPack;
    }

    getLineLocation(line) {
        return this.displayByProduct ? line.location_dest_id : super.getLineLocation(...arguments);
    }

    get displayDestinationLocation() {
        return (
            (this.groups.group_stock_multi_locations && this.displayByProduct) ||
            super.displayDestinationLocation
        );
    }

    lineCanBeSelected(line) {
        return this.displayByProduct || super.lineCanBeSelected(line);
    }

    lineCanBeEdited(line) {
        return this.displayByProduct || super.lineCanBeEdited(line);
    }

    /** Fetch data and set state */

    getActionRefresh(newId) {
        return {
            route: "/stock_barcode/get_barcode_data",
            params: { model: this.resModel, res_id: newId || this.resId },
        };
    }

    setData(data) {
        data.actionId = this.actionId || data.actionId;
        super.setData(...arguments);
        this.headerViewId = data.data.header_view_id;
        this.useTrackingNumber = true;
        if (this.config.restrict_scan_product) {
            this.validateContext.skip_compute_move_raw_ids = true;
        }
    }

    _getName() {
        if (!this.resId) {
            return _t("New");
        }
        return super._getName(...arguments);
    }

    async refreshCache(records) {
        if (!this.resId && "mrp.production" in records) {
            /** A new MO has no ID because it requires the finish product to be saved.
             * If there is no `resId` but a production belongs to the records, we assume this record
             * is the current MO who as been saved.
             */
            this.resId = records["mrp.production"]?.[0]?.id;
        }
        return super.refreshCache(...arguments);
    }

    _createState() {
        super._createState(...arguments);
        this.initialState.record = JSON.parse(JSON.stringify(this.record));
        this.trigger("update");
    }

    _getModelRecord() {
        const record = this.resId && this.cache.getRecord(this.resModel, this.resId);
        if (!record) {
            return {};
        }
        record.product_id = this.cache.getRecord("product.product", record.product_id);
        record.uom_id = this.cache.getRecord("uom.uom", record.uom_id);
        if (record.lot_producing_ids.length > 0) {
            for (const index in record.lot_producing_ids) {
                record.lot_producing_ids[index] = this.cache.getRecord(
                    "stock.lot",
                    record.lot_producing_ids[index]
                );
            }
        }
        if (record.picking_type_id && record.state !== "cancel") {
            record.picking_type_id = this.cache.getRecord(
                "stock.picking.type",
                record.picking_type_id
            );
        }
        return record;
    }

    _getMoveLineData(id) {
        const smlData = super._getMoveLineData(id);
        smlData.move_id = smlData.move_id && this.cache.getRecord("stock.move", smlData.move_id);
        return smlData;
    }

    _getLineMoveId(line) {
        return line.move_id.id;
    }

    _createLinesState() {
        const lines = [];
        if (!this.resId && !this.record.id) {
            return [];
        }
        const mo = this.cache.getRecord(this.resModel, this.resId || this.record.id);
        for (const id of mo.move_raw_line_ids) {
            lines.push(this._getMoveLineData(id));
        }
        for (const id of mo.move_byproduct_line_ids) {
            const line = this._getMoveLineData(id);
            line.byProduct = true;
            lines.push(line);
        }
        this.componentLoaded = true;
        return lines;
    }

    get reloadingMoveLines() {
        return super.reloadingMoveLines && this.componentLoaded;
    }

    async confirmAndSetData(recordId) {
        this.resId = recordId;
        await this.orm.call("mrp.production", "action_confirm", [[this.resId]]);
        const { route, params } = this.getActionRefresh(recordId);
        const result = await rpc(route, params);
        this.setData(result);
    }

    /** Line Operations */

    _checkBarcode(barcodeData) {
        if (this.displayByProduct && barcodeData?.product?.id == this.record.product_id.id) {
            return {
                title: _t("Product not Allowed"),
                message: _t("You can't add the final product of a MO as a byproduct."),
                error: true,
            };
        }
        return super._checkBarcode(...arguments);
    }

    _getFinalProductLine() {
        if (!this.record.virtualId) {
            this.record.virtualId = this._uniqueVirtualId;
        }
        if (this.record.location_dest_id && this.record.location_src_id) {
            return {
                virtual_id: this.record.virtualId,
                product_id: this.record.product_id,
                uom_id: this.record.uom_id,
                location_id: this.cache.getRecord("stock.location", this.record.location_src_id),
                location_dest_id: this.cache.getRecord(
                    "stock.location",
                    this.record.location_dest_id
                ),
                lot_id: this.record.lot_producing_ids?.length
                    ? this.record.lot_producing_ids.at(-1)
                    : false,
                lot_name: this.record.lot_name,
                finalProduct: true,
                package_id: false,
                qty_done: this.record.qty_producing,
                reserved_uom_qty: this.record.product_qty,
            };
        }
    }

    _findLine(barcodeData) {
        const { product } = barcodeData;
        if (this.record.product_id && product.id == this.record.product_id.id) {
            return this._getFinalProductLine();
        }
        return super._findLine(...arguments);
    }

    _getNewLineDefaultValues(fieldsParams) {
        const defaultValues = super._getNewLineDefaultValues(...arguments);
        delete defaultValues.picking_id;
        defaultValues.production_id = this.resId;
        if (this.displayByProduct) {
            defaultValues.byProduct = true;
        }
        return defaultValues;
    }

    _shouldSearchForAnotherLot(barcodeData, filters) {
        return !barcodeData.match && filters["stock.lot"];
    }

    _canOverrideTrackingNumber(line, newLotName) {
        if (line.finalProduct) {
            return true;
        }
        return super._canOverrideTrackingNumber(...arguments);
    }

    _shouldCreateLineOnExceed(line) {
        if (line.finalProduct) {
            return false;
        }
        return super._shouldCreateLineOnExceed(line);
    }

    async createNewLine(params) {
        const { product_id } = params.fieldsParams;
        if (!this.record.product_id && product_id) {
            this.record.product_id = product_id;
            this.trigger("playSound", "success");
            return await this.save();
        }
        return super.createNewLine(...arguments);
    }

    updateLine(line, args) {
        // handle header line updates here
        if (line.finalProduct) {
            if (this.record.product_id.tracking === "serial") {
                let lot = null;
                if (args.lot_id) {
                    lot = args.lot_id;
                } else if (args.lot_name) {
                    lot = {
                        name: args.lot_name,
                        product_id: this.record.product_id.id,
                        company_id: this.record.company_id,
                    };
                }
                if (lot) {
                    if (this.record.lot_producing_ids.some((l) => l.name === lot.name)) {
                        this.notification(
                            _t("The scanned serial number %s is already used.", lot.name),
                            { type: "danger" }
                        );
                        return;
                    }
                    this.record.lot_producing_ids = [...this.record.lot_producing_ids, lot];
                }
            } else {
                const lot =
                    args.lot_id ||
                    (args.lot_name && {
                        name: args.lot_name,
                        product_id: this.record.product_id.id,
                        company_id: this.record.company_id,
                    });
                if (lot) {
                    const currentLot = this.record.lot_producing_ids[0];
                    const sameLot = currentLot && currentLot.name === lot.name;
                    if (!sameLot) {
                        this.record.lot_producing_ids = [lot];
                        if (currentLot) {
                            args.qty_done = 0;
                        }
                    } else if (lot.id && !currentLot.id) {
                        this.record.lot_producing_ids = [lot];
                    }
                }
            }
            this.produceQty(args.qty_done);
            return;
        }
        let move = args.move_id;
        if (move) {
            if (typeof move === "number") {
                move = this.cache.getRecord("stock.move", move);
            }
            line.move_id = move;
        }
        args.picked = "picked" in args ? args.picked : true;
        super.updateLine(...arguments);
        if (args.move_uom_id) {
            line.uom_id = this.cache.getRecord("uom.uom", args.move_uom_id);
        }
    }

    updateLineQty(virtualId, qty = 1, picked = true, location_id = null) {
        this.actionMutex.exec(() => {
            const line = this.currentState.lines.find((l) => l.virtual_id === virtualId);
            this.updateLine(line, { picked, location_id, qty_done: qty });
            this.trigger("update");
        });
    }

    _updateLineQty(line, args) {
        line.picked = args.picked;
        super._updateLineQty(...arguments);
    }

    createSingleLinesForPackaging() {
        return false;
    }

    lineIsFaulty(line) {
        return line.reserved_uom_qty && line.qty_done > line.reserved_uom_qty;
    }

    _incrementTrackedLine() {
        return false;
    }

    _defaultLocation() {
        const locId = this.displayByProduct
            ? this.record.production_location_id
            : this.record.location_src_id;
        return this.cache.getRecord("stock.location", locId, false);
    }

    _defaultDestLocation() {
        const locId = this.displayByProduct
            ? this.record.location_dest_id
            : this.record.production_location_id;
        return this.cache.getRecord("stock.location", locId, false);
    }

    _getNewLineDefaultContext() {
        return {
            default_company_id: this.record.company_id,
            default_location_id: this._defaultLocation()?.id,
            default_location_dest_id: this._defaultDestLocation()?.id,
            default_production_id: this.resId,
            default_qty_done: 0,
            final_product_id: this.record.product_id?.id,
            newByProduct: this.displayByProduct,
            display_name: this.record.name,
            mark_picked: true,
        };
    }

    isManualConsumptionLine(line) {
        const parentLine = this._getParentLine(line);
        if (!parentLine) {
            return line.picked || !line.reserved_uom_qty;
        }
        for (const subLine of parentLine.lines) {
            if (subLine.picked || !subLine.reserved_uom_qty) {
                return true;
            }
        }
        return false;
    }

    async produceQty(quantity = 1) {
        this.record.qty_producing += quantity;
        const ratio = quantity / this.record.product_qty;

        for (const moveId of [...this.record.move_raw_ids, ...this.record.move_byproduct_ids]) {
            const move = this.cache.getRecord("stock.move", moveId);
            const product = this.cache.getRecord("product.product", move.product_id);
            const isComponent = this.record.move_raw_ids.includes(moveId);
            if (isComponent) {
                if (this.config.restrict_scan_product) {
                    // Don't automatically update move's qty if scanning the product is mandatory.
                    continue;
                } else if (
                    ["lot", "serial"].includes(product.tracking) &&
                    this.config.restrict_scan_tracking_number
                ) {
                    // Don't automatically update tracked component if scanning the lot/SN is mandatory.
                    continue;
                }
            }
            let manualMove = false;
            const moveLines = this.currentState.lines.filter((line) => line.move_id?.id === moveId);
            let qtyRemaining = ratio * move.product_uom_qty;
            for (const line of moveLines) {
                if (this.isManualConsumptionLine(line) || qtyRemaining === 0) {
                    manualMove = true;
                    break;
                }
                if (line.reserved_uom_qty <= 0) {
                    continue;
                }
                const qtyToAdd = Math.min(qtyRemaining, line.reserved_uom_qty);
                this.updateLineQty(line.virtual_id, qtyToAdd, false, line.location_id);
                qtyRemaining -= qtyToAdd;
            }
            if (qtyRemaining > 0 && !manualMove) {
                const fieldsParams = {
                    product_id: this.cache.getRecord("product.product", move.product_id),
                    location_id: move.location_id,
                    qty_done: qtyRemaining,
                    reserved_uom_qty: qtyRemaining,
                    move_id: moveId,
                };
                if (this.groups.group_uom) {
                    fieldsParams.move_uom_id = move.uom_id;
                }
                this._createNewLine({ fieldsParams });
            }
            if (this.groups.group_tracking_lot) {
                // Need to instantly update the final product in order to create
                // the correct move lines in backend and allow partial packing
                const finishedLinesIds = await this.orm.call(
                    "mrp.production",
                    "barcode_update_qty_producing",
                    [[this.resId], this.record.qty_producing]
                );
                this.record.finished_move_line_ids = finishedLinesIds;
            }
        }
        this.trigger("update");
    }

    async generateSerial() {
        const onClose = (e) => {
            if (e === undefined) {
                this.trigger("refresh");
            }
        };
        const context = { barcode_view: true };
        const params = { onClose };
        await this.save();
        const res = await this.orm.call("mrp.production", "set_lot_producing", [[this.resId]], {
            context,
        });
        const [lots, action] = res;
        if (lots) {
            this.record.lot_producing_ids = lots;
            if (this.record.product_id.tracking == "serial" && this.record.qty_producing === 0) {
                this.produceQty();
                if (action) {
                    return this.action.doAction(action, params);
                }
                return;
            }
        }
        if (action) {
            return this.action.doAction(action, params);
        }
        this.trigger("update");
    }

    async generateByproductLot(line) {
        const sequenceId = line.product_id.lot_sequence_id;
        if (sequenceId) {
            const lotName = await this.orm.call("ir.sequence", "next_by_id", [sequenceId]);
            const params = { lot_name: lotName };
            if (line.product_id.tracking === "serial" && !line.qty_done) {
                params.qty_done = 1;
            }
            await this.updateLine(line, params);
            this.trigger("update");
        }
    }

    displayLineQtyDemand(line) {
        if (!this.pageLines.includes(line)) {
            return true;
        }
        return super.displayLineQtyDemand(line);
    }

    /** Save commands */

    _getPrintOptions() {
        if (!this.resId) {
            return {};
        }
        return {
            additionalContext: {
                active_ids: [this.resId],
            },
        };
    }

    _getFieldToWrite() {
        const fields = super._getFieldToWrite(...arguments);
        fields.push("picked");
        return fields;
    }

    _getSaveCommand() {
        // only need the last two arguments (id / 0 and vals) from each command
        const commands = this._getSaveLineCommand().map((cmd) => [this.lineModel, cmd[1], cmd[2]]);
        // we need a product before we can create an MO
        if (this.record.product_id) {
            const vals = this._getRecordSaveVals();
            if (Object.keys(vals).length) {
                commands.push([this.resModel, this.resId || 0, vals]);
            }
        }
        if (commands.length) {
            return {
                route: "/stock_barcode_mrp/save_barcode_data",
                params: {
                    model_vals: commands,
                },
            };
        }
        return {};
    }

    _getRecordFieldsToWrite() {
        return ["qty_producing", "product_qty", "lot_producing_ids", "product_id"];
    }

    _getRecordSaveVals() {
        // compare current record with initial value;
        const res = {};
        const writeFields = this._getRecordFieldsToWrite();
        for (const fieldName of writeFields) {
            let value = this.record[fieldName];
            if (Array.isArray(value)) {
                value = value.map((value) => value.id);
            } else if (typeof value === "object") {
                value = value.id;
            }
            let initialValue = this.initialState.record[fieldName];
            if (Array.isArray(initialValue)) {
                initialValue = initialValue.map((initialValue) => initialValue.id);
            } else if (typeof initialValue === "object") {
                initialValue = initialValue.id;
            }
            if (!deepEqual(value, initialValue)) {
                res[fieldName] = value;
            }
        }
        if (this.record.lot_name && this.record.lot_producing_ids.length == 0) {
            res.lot_producing_ids = [
                {
                    name: this.record.lot_name,
                    product_id: this.record.product_id.id,
                    company_id: this.record.company_id, // only the id is fetched from the backend
                },
            ];
        }
        const lots = this.record.lot_producing_ids;
        if (Array.isArray(res.lot_producing_ids) && lots.some((l) => !l.id)) {
            const existingIds = lots.filter((l) => l.id).map((l) => l.id);
            const newLots = lots.filter((l) => !l.id);
            res.lot_producing_ids = [
                x2ManyCommands.set(existingIds),
                ...newLots.map((l) => x2ManyCommands.create(false, l)),
            ];
        }

        if (!this.record.company_id) {
            res.company_id = this._getCompanyId();
        }
        if (!this.record.picking_type_id) {
            res.picking_type_id = this.picking_type_id;
        }
        return res;
    }

    _createCommandVals(line) {
        const values = super._createCommandVals(...arguments);
        values.production_id = this.resId;
        values.company_id = this.record.company_id;
        if (line.byProduct) {
            values.byProduct = true;
        }
        return values;
    }

    _getCommands() {
        return Object.assign(super._getCommands(), {
            OBTPRMO: this.print.bind(this, "mrp.action_report_production_order"),
            OBTPRPL: this.print.bind(this, "mrp.action_print_finished_product_pdf"),
        });
    }

    _getCompanyId() {
        const defaultCompanyId = this.action.currentController.action.context["default_company_id"];
        const userCompanyId = user.defaultCompany.id;
        return defaultCompanyId || userCompanyId;
    }

    async _putInPack(additionalParams = {}, splitLines = true) {
        if (!this.resId) {
            const message = _t("You are expected to scan one or more products.");
            this.notification(message, { type: "danger" });
            return;
        }
        additionalParams.move_line_ids = false;
        splitLines = false;
        if (this.displayByProduct) {
            additionalParams.move_line_ids =
                this.selectedLine?.move_id?.move_line_ids || this.record.move_byproduct_line_ids;
            splitLines = true;
        }
        return super._putInPack(additionalParams, splitLines);
    }

    getPutInPackParams(params) {
        return {
            ...super.getPutInPackParams(params),
            move_line_ids: params.move_line_ids,
        };
    }

    mustTryPackUnscannedLine() {
        return !this.resId && super.mustTryPackUnscannedLine();
    }

    _putInPackaging() {
        return false;
    }
}
