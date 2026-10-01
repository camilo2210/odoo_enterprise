import BarcodeModel from "@stock_barcode/models/barcode_model";
import { BackorderDialog } from "../components/backorder_dialog";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ExtraProductDialog } from "../components/extra_product_dialog";
import { SuggestBatchDialog } from "../components/suggest_batch_dialog";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { markup, proxy } from "@odoo/owl";
import { SignatureDialog } from "@web/core/signature/signature_dialog";
import { useService } from "@web/core/utils/hooks";

export default class BarcodePickingModel extends BarcodeModel {
    constructor(resModel, resId, services) {
        super(resModel, resId, services);
        this.lineModel = "stock.move.line";
        this.showBackOrderDialog = true;
        this.validateMessage = _t("The transfer has been validated");
        this.validateMethod = "button_validate";
        this.deleteLineMethod = "unlink";
        this.validateContext = {
            display_detailed_backorder: true,
            skip_backorder: true,
        };
        this.lastScanned.destLocation = false;
        this.shouldShortenLocationName = true;
        this.actionName = "stock_barcode.stock_barcode_picking_client_action";
        this.backorderModel = "stock.picking";
        this.needSourceConfirmation = {};
        this.ui = useService("ui");
        this.extraProducts = proxy(new Map());
    }

    setData(data) {
        super.setData(...arguments);
        const { use_create_lots, use_existing_lots } = this.record.picking_type_id || {};
        this.useTrackingNumber = use_create_lots || use_existing_lots;
        if (!this.useScanDestinationLocation) {
            this.config.restrict_scan_dest_location = "no";
        }
        this.lineFormViewId = data.data.line_view_id;
        this.formViewId = data.data.form_view_id;
        this.scrapViewId = data.data.scrap_view_id;
        this.packageKanbanViewId = data.data.package_view_id;
        this.precision = data.data.precision;

        this.candidatePickingsToBatch = data.data.candidate_pickings_to_batch || [];

        if (this.config?.allocated_location_id) {
            const locationId = this.config.allocated_location_id;
            this.allocatedLocation = this.cache.getRecord("stock.location", locationId);
        }
        if (this._useReservation === undefined) {
            this._useReservation = this.initialState.lines.some((line) => !line.picked);
        }
        if (this._allowExtraProduct === undefined) {
            this._allowExtraProduct = Boolean(
                this.config.barcode_allow_extra_product === undefined ||
                    this.config.barcode_allow_extra_product ||
                    (!this._useReservation && this.record.state === "draft")
            );
        }
    }

    setConfig() {
        super.setConfig(...arguments);
        if (this.record && !this.useScanDestinationLocation) {
            this.config.restrict_scan_dest_location = "no";
        }
    }

    askBeforeNewLinesCreation(product) {
        return (
            this._useReservation &&
            product &&
            !this.currentState.lines.some((line) => line.product_id.id === product.id)
        );
    }

    createNewLine(params) {
        const product = params.fieldsParams.product_id;
        if (this.needSourceConfirmation[this.location.id]?.[product.id]) {
            const message = _t(
                "You are about to take the product %(productName)s from the " +
                    "location %(locationName)s but this product isn't reserved in this location.\n" +
                    "Scan the current location to confirm that.",
                { productName: product.display_name, locationName: this.location.display_name }
            );
            this.needSourceConfirmation[this.location.id][product.id] = false;
            this.notification(message, { type: "danger" });
            return false;
        } else if (
            !this._allowExtraProduct &&
            !this.currentState.lines.some((line) => line.product_id.id === product.id)
        ) {
            // No unreserved product can't be added, display a warning.
            const productName = (product.code ? `[${product.code}] ` : "") + product.display_name;
            const message = _t(
                "The product %s should not be picked in this operation.",
                productName
            );
            this.notification(message, { type: "danger" });
            return false;
        }
        if (this.askBeforeNewLinesCreation(product)) {
            // Unreserved product can be added but a confirmation is needed.
            return this._addInConfirmationQueue(params);
        }
        return super.createNewLine(...arguments);
    }

    _addInConfirmationQueue(params) {
        const { product_id: product, qty_done, uom } = params.fieldsParams;
        const productInQueue = this.extraProducts.get(product.id);
        if (productInQueue) {
            // The scanned product is already in the confirmation queue: update its params.
            const existingLotIndex = productInQueue.params.findIndex((p) => {
                const { lot_name, lot_id } = p.fieldsParams;
                return (
                    (lot_name && lot_name === params.fieldsParams.lot_name) ||
                    (lot_id && lot_id === params.fieldsParams.lot_id)
                );
            });
            const isRedundantLot = existingLotIndex !== -1;
            // If the product is tracked by serial number and the scanned serial number is already in params, skip it to avoid duplicates in the dialog.
            if (product.tracking === "serial" && isRedundantLot) {
                const lotName =
                    params.fieldsParams.lot_name ||
                    this.cache.getRecord("stock.production.lot", params.fieldsParams.lot_id).name;
                const message = _t(
                    "The scanned serial number %(lotName)s is already awaiting confirmation.",
                    { lotName }
                );
                return this.notification(message, { type: "danger" });
            }
            productInQueue.qty += qty_done;
            if (product.tracking === "lot" && isRedundantLot) {
                // For an already scanned lot, update the quantity without adding a new line.
                productInQueue.params[existingLotIndex].fieldsParams.qty_done += qty_done;
            } else {
                productInQueue.params.push(params);
            }
        } else {
            // The product isn't in the confirmation queue, check if the scanned product is waited
            // by at least one another operation which could be batched with this operation.
            const candidates = this.candidatePickingsToBatch.filter((picking) =>
                picking.product_ids.includes(product.id)
            );
            if (candidates.length) {
                // If there is at least on good candidate, ask the user if they want to
                // batch this operation with another one which waits the scanned product.
                const productName = product.code
                    ? `[${product.code}] ${product.display_name}`
                    : product.display_name;
                const body = _t(
                    "%(product)s was not expected for this receipt but can be found in other waiting receipts ",
                    { product: productName }
                );
                const title = _t("Batch Receipts from %(partner)s?", {
                    partner: candidates[0].partner_name,
                });
                this.dialogService.add(SuggestBatchDialog, {
                    body,
                    candidates,
                    product,
                    title,
                    addProduct: this._confirmExtraProductDialog.bind(this),
                    cancel: this.extraProducts.clear,
                    close: this.extraProducts.clear,
                    confirm: (selectedPicking) => {
                        const kwargs = { product_id: product.id, qty_done, uom_id: uom?.id };
                        return this._applyBatch(selectedPicking, kwargs);
                    },
                });
            } else if (!this.extraProducts.size) {
                // If there is no product yet, display the confirmation dialog.
                this.dialogService.add(ExtraProductDialog, {
                    products: this.extraProducts,
                    cancel: this.extraProducts.clear,
                    confirm: this._confirmExtraProductDialog.bind(this),
                    close: this.extraProducts.clear,
                });
            }
            this.extraProducts.set(product.id, {
                name: (product.code ? `[${product.code}] ` : "") + product.display_name,
                qty: qty_done,
                uomName: this.cache.getRecord("uom.uom", product.uom_id).name,
                confirmed: true,
                params: [params],
            });
        }
        this.trigger("playSound");
        return false;
    }

    /**
     * Batch current picking with given picking(s) and open straight away the batch.
     * @param {Array} pickingIds list of pickings' id to batch with current picking
     */
    async _applyBatch(selectedPicking, kwargs) {
        await this.beforeQuit();
        const batchAction = await this.orm.call(
            "stock.picking",
            "action_batch_pickings_from_barcode",
            [this.pickingIds, [selectedPicking.id]],
            kwargs
        );
        return this.action.doAction(batchAction, {
            stackPosition: "replaceCurrentAction",
        });
    }

    async _confirmExtraProductDialog() {
        let newLine;
        for (const productData of this.extraProducts.values()) {
            if (!productData.confirmed) {
                continue;
            }
            for (const lineParams of productData.params) {
                const { lot_name, lot_id } = lineParams.fieldsParams;
                if (!newLine || lot_name || lot_id) {
                    newLine = await this._createNewLine(lineParams);
                } else {
                    await this.updateLine(newLine, lineParams.fieldsParams);
                }
            }
        }
        if (newLine) {
            this.trigger("playSound", "success");
            this._selectLine(newLine);
            this.trigger("update");
        }
        this.extraProducts.clear();
        this.trigger("update");
    }

    getDisplayCompletePackageBtn(line) {
        return line.isPackageLine;
    }

    getDisplayIncrementBtn(line) {
        line = (line.product_id.tracking === "lot" && this._getParentLine(line)) || line;
        return !this.getQtyDemand(line) || this.getQtyDone(line) < this.getQtyDemand(line);
    }

    getDisplayIncrementBtnForSerial(line) {
        const lineTrackingNumber = line.lot_id || line.lot_name;
        return (
            !this.useTrackingNumber ||
            (!this.config.restrict_scan_tracking_number &&
                lineTrackingNumber &&
                this.getQtyDone(line) === 0)
        );
    }

    getLineRemainingQuantity(line) {
        const remainingQty = super.getLineRemainingQuantity(...arguments);
        const parentLine =
            (line.product_id.tracking === "lot" && this._getParentLine(line)) || line;
        if (parentLine && this.getQtyDemand(parentLine)) {
            const parentRemainingQty = this.getQtyDemand(parentLine) - this.getQtyDone(parentLine);
            if (parentRemainingQty) {
                return Math.min(Math.max(1, remainingQty), parentRemainingQty);
            }
        }
        return remainingQty;
    }

    getQtyDone(line) {
        return line.qty_done;
    }

    getQtyDemand(line) {
        return line.reserved_uom_qty || 0;
    }

    getEditedLineParams(line) {
        this._setUser();
        return super.getEditedLineParams(...arguments);
    }

    completePackage(virtualId) {
        this.actionMutex.exec(() => {
            const packageLine = this.packageLines.find((l) => l.virtual_id === virtualId);
            const factor = packageLine.qty_done ? -1 : 1;
            for (const line of packageLine.lines) {
                this.selectedLineVirtualId = line.virtual_id;
                const lineQty = line.reserved_uom_qty || line.qty_done || line.packedQuantity;
                this._updateLineQty(line, { qty_done: lineQty * factor });
                this._markLineAsDirty(line);
            }
            this.trigger("update");
        });
    }

    displayLinePrintReservation(line) {
        if (
            this.allocatedLocation &&
            this._isSublocation(line.location_dest_id, this.allocatedLocation)
        ) {
            return true;
        }
        return super.displayLinePrintReservation(...arguments);
    }

    displayLineQtyDemand(line) {
        if (line.isPackageLine && line.reservedPackage) {
            return true;
        } else if (!this.showReservedSns) {
            return (
                this.getQtyDemand(line) &&
                !(this.lineIsTracked(line) && !line.lines && this._getParentLine(line))
            );
        }
        return super.displayLineQtyDemand(line);
    }

    groupKey(line) {
        const key = super.groupKey(...arguments) + `_${line.location_dest_id.id}`;
        return this.mustGroupSameProductLines() ? key : `${line.move_id}_${key}`;
    }

    lineCanBeSelected(line) {
        if (
            this.config.restrict_scan_source_location &&
            ((!this.lastScanned.sourceLocation && !line.qty_done) ||
                this.lastScanned.sourceLocation.id !== line.location_id.id)
        ) {
            return false; // Can't select a line if source is mandatory and wasn't scanned yet.
        }
        if (this.selectedLine && this.selectedLine.virtual_id === line.virtual_id) {
            return true; // We consider an already selected line can always be re-selected.
        }
        if (line.isPackageLine) {
            // The next conditions concern product, skips them in case of package line.
            return super.lineCanBeSelected(...arguments);
        }
        const product = line.product_id;
        if (
            this.config.restrict_put_in_pack === "mandatory" &&
            this.selectedLine &&
            this.selectedLine.qty_done &&
            !this.selectedLine.result_package_id &&
            this.selectedLine.product_id.id != product.id
        ) {
            return false; // Can't select another product if a package must be scanned first.
        }
        if (this.config.restrict_scan_product && product.barcode) {
            // If the product scan is mandatory, a line can't be selected if its product isn't
            // scanned first (as we can't keep track of each line's product scanned state, we
            // consider a product was scanned if the line has a qty. greater than zero).
            if (
                !["lot", "serial"].includes(product.tracking) ||
                !this.config.restrict_scan_tracking_number
            ) {
                return (
                    !this.getQtyDemand(line) ||
                    this.getQtyDone(line) ||
                    (this.lastScanned.product && this.lastScanned.product.id === line.product_id.id)
                );
            } else if (["lot", "serial"].includes(product.tracking)) {
                return line.lot_name || (line.lot_id && line.qty_done);
            }
        }
        return super.lineCanBeSelected(...arguments);
    }

    lineCanBeEdited(line) {
        if (
            this.config.restrict_scan_product &&
            line.product_id.barcode &&
            !this.getQtyDone(line) &&
            (!this.lastScanned.product || this.lastScanned.product.id != line.product_id.id)
        ) {
            return false;
        }
        if (
            ["lot", "serial"].includes(line.product_id.tracking) &&
            this.config.restrict_scan_tracking_number &&
            !((line.lot_id && line.qty_done) || line.lot_name)
        ) {
            return false;
        }
        return this.lineCanBeSelected(line);
    }

    /**
     * Check if the given line can be packed into the given package.
     * @param {Object} line
     * @param {Object} recPackage
     * @returns boolean
     */
    lineCanBePackedIntoPackage(line, recPackage) {
        if (line && recPackage) {
            const packageHasContent = Boolean(
                recPackage.contained_quant_ids.length ||
                    this._findConsumableLinesFromPackage(recPackage).length
            );
            if (packageHasContent && recPackage.location_id !== line.location_dest_id.id) {
                // The result package is in another location -> Can't pack into it.
                return false;
            }
            if (!line.result_package_id || !packageHasContent) {
                // Can always pack an unpacked line or put in pack if result package is empty.
                return true;
            }
            if (
                line.result_package_id.package_type_id &&
                recPackage.package_type_id &&
                line.result_package_id.package_type_id.id !== recPackage.package_type_id.id &&
                !line.outermost_result_package_id
            ) {
                // Can pack a packed line inside another package if they have different package type
                return true;
            }
        }
        return false;
    }

    lineCanBeTakenFromTheCurrentLocation(line) {
        // A line with no qty. done can be taken regardless its location (it will be overridden).
        const res =
            !this.getQtyDone(line) || super.lineCanBeTakenFromTheCurrentLocation(...arguments);
        // If source location's scan is mandatory, the source should be confirmed (scanned once
        // again) to confirm we want to take this product from the current location.
        if (
            res &&
            this.config.restrict_scan_source_location &&
            line.location_id.id !== this.location.id &&
            this.lineIsReserved(line)
        ) {
            if (this.needSourceConfirmation[this.location.id] === undefined) {
                this.needSourceConfirmation[this.location.id] = {};
            }
            if (
                !this.scanHistory[1].location ||
                this.scanHistory[1].location.id !== this.location.id
            ) {
                this.needSourceConfirmation[this.location.id][line.product_id.id] = true;
                return false;
            }
            // The source was scanned just before, no need to confirm it for this product anymore.
            this.needSourceConfirmation[this.location.id][line.product_id.id] = false;
        }
        return res;
    }

    lineIsReserved(line) {
        return !line.picked && line.quantity;
    }

    locationNeedsAttention(location) {
        // Override to return true if the location isn't a sublocation of the operation's source.
        if (this.record) {
            return !this._isSublocation(location, this.operationSourceLocation);
        }
        return super.locationNeedsAttention(...arguments);
    }

    mustGroupSameProductLines() {
        return false;
    }

    async updateLine(line, args) {
        await super.updateLine(...arguments);
        let { location_id, location_dest_id, is_entire_pack } = args;
        if ("result_package_id" in args) {
            let resultPackage = args.result_package_id;
            if (typeof resultPackage === "number") {
                resultPackage = this.cache.getRecord("stock.package", resultPackage);
            }
            if (
                resultPackage.package_type_id &&
                typeof resultPackage.package_type_id === "number"
            ) {
                resultPackage.package_type_id = this.cache.getRecord(
                    "stock.package.type",
                    resultPackage.package_type_id
                );
            }
            line.result_package_id = resultPackage;
        }
        if ("outermost_result_package_id" in args) {
            let outermostResultPackage = args.outermost_result_package_id;
            if (typeof outermostResultPackage === "number") {
                outermostResultPackage = this.cache.getRecord(
                    "stock.package",
                    outermostResultPackage
                );
            }
            line.outermost_result_package_id = outermostResultPackage;
            if (
                line.result_package_id &&
                !line.result_package_id.dest_complete_name.includes(outermostResultPackage.name)
            ) {
                // The `result_package_id` `dest_complete_name` won't be
                // recomputed until next save, so we have to compute it JS side.
                line.result_package_id.dest_complete_name = `${outermostResultPackage.name} > ${line.result_package_id.name}`;
            }
        }
        if (!args.dontUpdateSourceLocation && !location_id && this.lastScanned.sourceLocation) {
            line.location_id = this.lastScanned.sourceLocation;
            if (line.package_id && line.package_id.location_id != line.location_id.id) {
                line.package_id = false;
            }
        }
        if (location_dest_id) {
            if (typeof location_dest_id === "number") {
                location_dest_id = this.cache.getRecord("stock.location", args.location_dest_id);
            }
            line.location_dest_id = location_dest_id;
        }
        if (is_entire_pack) {
            line.is_entire_pack = is_entire_pack;
        }
    }

    updateLineQty(virtualId, qty = 1) {
        this.actionMutex.exec(() => {
            const line = this.pageLines.find((l) => l.virtual_id === virtualId);
            this.updateLine(line, { qty_done: qty });
            this.trigger("update");
        });
    }

    get backordersDomain() {
        return [["backorder_id", "=", this.resId]];
    }

    get barcodeInfo() {
        if (this.isCancelled || this.isDone) {
            return {
                class: this.isDone ? "picking_already_done" : "picking_already_cancelled",
                message: this.isDone
                    ? _t("This picking is already done")
                    : _t("This picking is cancelled"),
                icon: "warning",
                warning: true,
            };
        }
        // Takes the parent line if the current line is part of a group.
        const parentLine = this._getParentLine(this.selectedLine);
        const line = parentLine && this.getQtyDemand(parentLine) ? parentLine : this.selectedLine;
        // Defines some messages who can appear in multiple cases.
        const infos = {
            scanScrLoc: {
                message:
                    this.considerPackageLines && !this.config.restrict_scan_source_location
                        ? _t("Scan the source location or a package")
                        : _t("Scan the source location"),
                class: "scan_src",
                icon: "logout",
            },
            scanDestLoc: {
                message: _t("Scan the destination location"),
                class: "scan_dest",
                icon: "login",
            },
            scanProductOrDestLoc: {
                message: this.considerPackageLines
                    ? _t("Scan a product, a package or the destination location.")
                    : _t("Scan a product or the destination location."),
                class: "scan_product_or_dest",
            },
            scanPackage: {
                message: this._getScanPackageMessage(line),
                class: "scan_package",
                icon: "archive",
            },
            scanLot: {
                message: _t("Scan a lot number"),
                class: "scan_lot",
                icon: "barcode",
            },
            scanSerial: {
                message: _t("Scan a serial number"),
                class: "scan_serial",
                icon: "barcode",
            },
            pressValidateBtn: {
                message: _t("Press Validate or scan another product"),
                class: "scan_validate",
                icon: "check_box",
                iconClass: "oi-filled",
            },
        };
        let barcodeInfo = {
            message: _t("Scan a product"),
            class: "scan_product",
            icon: "sell",
        };
        if ((line || this.lastScanned.packageId) && this.groups.group_stock_multi_locations) {
            if (this.record.picking_type_code === "outgoing" && this.useScanSourceLocation) {
                barcodeInfo = {
                    message: _t("Scan more products, or scan a new source location"),
                    class: "scan_product_or_src",
                };
            } else if (this.config.restrict_scan_dest_location != "no") {
                barcodeInfo = infos.scanProductOrDestLoc;
            }
        }

        if (!line && this._moveEntirePackage()) {
            // About package lines.
            const packageLine = this.selectedPackageLine;
            if (packageLine) {
                if (this._lineIsComplete(packageLine)) {
                    if (
                        this.config.restrict_scan_source_location &&
                        !this.lastScanned.sourceLocation
                    ) {
                        return infos.scanScrLoc;
                    } else if (
                        this.config.restrict_scan_dest_location != "no" &&
                        !this.lastScanned.destLocation
                    ) {
                        return this.config.restrict_scan_dest_location == "mandatory"
                            ? infos.scanDestLoc
                            : infos.scanProductOrDestLoc;
                    } else if (this.pageIsDone) {
                        return infos.pressValidateBtn;
                    } else {
                        barcodeInfo.message = _t("Scan a product or another package");
                        barcodeInfo.class = "scan_product_or_package";
                    }
                } else {
                    barcodeInfo.message = _t(
                        "Scan the package %s",
                        packageLine.result_package_id.name
                    );
                    barcodeInfo.icon = "archive";
                }
                return barcodeInfo;
            } else if (this.considerPackageLines && barcodeInfo.class == "scan_product") {
                barcodeInfo.message = _t("Scan a product or a package");
                barcodeInfo.class = "scan_product_or_package";
            }
        }
        if (
            barcodeInfo.class === "scan_product" &&
            !(line || this.lastScanned.packageId) &&
            this.config.restrict_scan_source_location &&
            this.lastScanned.sourceLocation
        ) {
            barcodeInfo.message = _t(
                "Scan a product from %s",
                this.lastScanned.sourceLocation.name
            );
        }

        // About source location.
        if (this.useScanSourceLocation) {
            if (!this.lastScanned.sourceLocation && !this.pageIsDone) {
                return infos.scanScrLoc;
            } else if (
                this.lastScanned.sourceLocation &&
                this.lastScanned.destLocation == "no" &&
                line &&
                this._lineIsComplete(line)
            ) {
                if (this.config.restrict_put_in_pack === "mandatory" && !line.result_package_id) {
                    return {
                        message: _t("Scan a package"),
                        class: "scan_package",
                        icon: "archive",
                    };
                }
                return infos.scanScrLoc;
            }
        }

        if (!line) {
            if (this.pageIsDone) {
                // All is done, says to validate the transfer.
                return infos.pressValidateBtn;
            } else if (this.config.lines_need_to_be_packed) {
                const lines = new Array(...this.pageLines, ...this.packageLines);
                if (
                    lines.every((line) => !this._lineIsNotComplete(line)) &&
                    lines.some((line) => this._lineNeedsToBePacked(line))
                ) {
                    return infos.scanPackage;
                }
            }
            return barcodeInfo;
        }
        const product = line.product_id;

        // About tracking numbers.
        if (
            ["lot", "serial"].includes(product.tracking) &&
            (this.record.picking_type_id.use_create_lots ||
                this.record.picking_type_id.use_existing_lots)
        ) {
            const isLot = product.tracking === "lot";
            if (this.getQtyDemand(line) && (line.lot_id || line.lot_name)) {
                // Reserved.
                if (this.getQtyDone(line) === 0) {
                    // Lot/SN not scanned yet.
                    return isLot ? infos.scanLot : infos.scanSerial;
                } else if (this.getQtyDone(line) < this.getQtyDemand(line)) {
                    // Lot/SN scanned but not enough.
                    barcodeInfo = isLot ? infos.scanLot : infos.scanSerial;
                    barcodeInfo.message = isLot
                        ? _t("Scan more lot numbers")
                        : _t("Scan another serial number");
                    return barcodeInfo;
                }
            } else if (!(line.lot_id || line.lot_name)) {
                // Not reserved.
                return isLot ? infos.scanLot : infos.scanSerial;
            }
        }

        // About package.
        if (this._lineNeedsToBePacked(line)) {
            if (this._lineIsComplete(line)) {
                return infos.scanPackage;
            }
            if (product.tracking == "serial") {
                barcodeInfo.message = _t("Scan a serial number or a package");
            } else if (product.tracking == "lot") {
                barcodeInfo.message =
                    line.qty_done == 0
                        ? _t("Scan a lot number")
                        : _t("Scan more lot numbers or a package");
                barcodeInfo.class = "scan_lot";
            } else {
                barcodeInfo.message = _t("Scan more products or a package");
            }
            return barcodeInfo;
        }

        if (this.pageIsDone) {
            barcodeInfo = infos.pressValidateBtn;
        }

        // About destination location.
        const lineWaitingPackage =
            this.groups.group_tracking_lot &&
            this.config.restrict_put_in_pack != "no" &&
            !line.result_package_id;
        if (this.config.restrict_scan_dest_location != "no" && line.qty_done) {
            if (this.pageIsDone) {
                if (this.lastScanned.destLocation) {
                    return infos.pressValidateBtn;
                } else {
                    return this.config.restrict_scan_dest_location == "mandatory" &&
                        this._lineIsComplete(line)
                        ? infos.scanDestLoc
                        : infos.scanProductOrDestLoc;
                }
            } else if (this._lineIsComplete(line)) {
                if (lineWaitingPackage) {
                    barcodeInfo.message =
                        this.config.restrict_scan_dest_location == "mandatory"
                            ? _t("Scan a package or the destination location")
                            : _t("Scan a package, the destination location or another product");
                } else {
                    return this.config.restrict_scan_dest_location == "mandatory"
                        ? infos.scanDestLoc
                        : infos.scanProductOrDestLoc;
                }
            } else {
                barcodeInfo = infos.scanProductOrDestLoc;
                if (product.tracking == "serial") {
                    barcodeInfo.message = lineWaitingPackage
                        ? _t("Scan a serial number or a package then the destination location")
                        : _t("Scan a serial number then the destination location");
                } else if (product.tracking == "lot") {
                    barcodeInfo.message = lineWaitingPackage
                        ? _t("Scan a lot number or a packages then the destination location")
                        : _t("Scan a lot number then the destination location");
                } else {
                    barcodeInfo.message = lineWaitingPackage
                        ? _t("Scan a product, a package or the destination location")
                        : _t("Scan a product then the destination location");
                }
            }
        }

        return barcodeInfo;
    }

    get canBeProcessed() {
        return !["cancel", "done"].includes(this.record.state);
    }

    get displaySignatureButton() {
        return (
            this.record.picking_type_code === "outgoing" &&
            !this.record.signature &&
            this.groups.group_stock_sign_delivery
        );
    }

    /**
     * Depending of the config, a transfer can be fully validate even if nothing was scanned (like
     * with an immediate transfer) or if at least one product was scanned.
     * @returns {boolean}
     */
    get canBeValidate() {
        if (!this._useReservation) {
            return super.canBeValidate; // For immediate transfers, doesn't care about any special condition.
        } else if (
            !this.config.barcode_validation_full &&
            !this.currentState.lines.some((line) => line.qty_done)
        ) {
            return false; // Can't be validate because "full validation" is forbidden and nothing was processed yet.
        }
        return super.canBeValidate;
    }

    get cancelLabel() {
        return _t("Cancel Transfer");
    }

    get canCreateNewLot() {
        return this.record.use_create_lots;
    }

    get showReservedSns() {
        if (this.canCreateNewLot && !this.useExistingLots) {
            return false;
        }
        return this.record.picking_type_id.show_reserved_sns;
    }

    get canPutInPack() {
        if (this.config.restrict_scan_product) {
            return this.pageLines.some(
                (line) =>
                    line.qty_done && (!line.result_package_id || !line.outermost_result_package_id)
            );
        }
        return Boolean(this.pageLines.length);
    }

    get canScrap() {
        const { picking_type_code, state } = this.record;
        return (
            (picking_type_code === "incoming" && state === "done") ||
            (picking_type_code === "outgoing" && state !== "done") ||
            picking_type_code === "internal"
        );
    }

    get scrapContext() {
        const context = this._getNewLineDefaultContext();
        delete context.force_fullfil_quantity;
        delete context.default_qty_done;
        const moves = this.record.move_ids.map((id) => this.cache.getRecord("stock.move", id));
        context["product_ids"] = moves.map((move) => move.product_id);
        context["default_location_id"] = this.cache.getRecord(
            "stock.location",
            this.record.location_dest_id
        );
        context["default_location_dest_id"] = this._defaultScrapLocation().id;
        context["default_quantity"] = 1.0;
        context["default_is_scrap"] = true;
        return context;
    }

    get canSelectLocation() {
        return !(
            this.config.restrict_scan_source_location ||
            this.config.restrict_scan_dest_location != "optional"
        );
    }

    shouldSplitLine(line) {
        if (!line.qty_done || !line.reserved_uom_qty || line.qty_done >= line.reserved_uom_qty) {
            return false; // No need to split a completed line or a line with no reservation.
        }
        line = this._getParentLine(line) || line;
        return line.qty_done && line.reserved_uom_qty && line.qty_done < line.reserved_uom_qty;
    }

    /**
     * Splits a line if its qty done is less than reserved.
     * In case of a grouped line, if there's is a lot id or product tracking is serial,
     * the new line doesn't need to be splitted since there is an existing line
     * that will be grouped seperately after location is changed.
     * @param {Object} line to split
     * @param {number} [splitQty] line.qty_done by default
     * @returns {boolean|Object} Returns the new splitted line or false if line can't be split.
     */
    async splitLine(line, splitQty) {
        if (!this.shouldSplitLine(line)) {
            return false;
        }
        // Use line's locations otherwise the picking's locations are used as default locations.
        const fieldsParams = {
            location_id: line.location_id.id,
            location_dest_id: line.location_dest_id.id,
            package_id: line.package_id?.id,
            picking_id: line.picking_id,
        };
        const affectQtyDone = splitQty && line.qty_done > splitQty;
        splitQty = splitQty || line.qty_done; // Line's qty_done as default value.
        const newLine = await this._createNewLine({ copyOf: line, fieldsParams });
        delete newLine.parentLine;
        // Update the reservation of the both old and new lines.
        newLine.reserved_uom_qty = line.reserved_uom_qty - splitQty;
        line.reserved_uom_qty = splitQty;
        // In case we split the line on a forced quantity, adapt lines' `qty_done` if needed.
        if (affectQtyDone) {
            const exceedingQuantity = line.qty_done - splitQty;
            line.qty_done -= exceedingQuantity;
            newLine.qty_done = exceedingQuantity;
        }
        // Be sure the new line has no lot by default.
        newLine.lot_id = false;
        newLine.lot_name = false;

        return newLine;
    }

    /**
     * The line's destination is changed to the given location, and if the line's reservation isn't
     * fulfilled, the remaining qties are moved to a new line with the original destination location.
     *
     * @param {int} id location's id
     */
    async changeDestinationLocation(id, selectedLine) {
        if (selectedLine.lines && !selectedLine.isPackageLine) {
            this._clearScanData();
            return false;
        }
        if (!selectedLine.lot_id) {
            await this.splitLine(selectedLine);
        }
        // If the line has no reservation and is grouped with sibling lines,
        // checks if we can assign to it a part of the reservation.
        const parentLine = this._getParentLine(selectedLine);
        if (
            selectedLine.product_id.tracking === "lot" &&
            parentLine &&
            selectedLine.qty_done &&
            !selectedLine.reserved_uom_qty
        ) {
            // Searches for a line with uncomplete reservation.
            const uncompletedLine = parentLine.lines.find(
                (line) => line.reserved_uom_qty && line.qty_done < line.reserved_uom_qty
            );
            if (uncompletedLine) {
                // Checks if a portion of the reservation can be assign to the current line.
                const remainingQty = Math.max(
                    0,
                    uncompletedLine.reserved_uom_qty - uncompletedLine.qty_done
                );
                const stolenReservation = Math.min(remainingQty, selectedLine.qty_done);
                if (stolenReservation) {
                    // Assigns the reservation on the current line.
                    uncompletedLine.reserved_uom_qty -= stolenReservation;
                    selectedLine.reserved_uom_qty = stolenReservation;
                }
            }
        }
        selectedLine.location_dest_id = this.cache.getRecord("stock.location", id);
        selectedLine.lastScannedDestination = selectedLine.location_dest_id;
        this._markLineAsDirty(selectedLine);
        this._clearScanData();
        return true;
    }

    _clearScanData() {
        this.selectedLineVirtualId = false;
        this.location = false;
        this.lastScanned.packageId = false;
        this.lastScanned.product = false;
        this.scannedLinesVirtualId = [];
    }

    get considerPackageLines() {
        return this._moveEntirePackage() && this.packageLines.length;
    }

    get displayAddProductButton() {
        return this._allowExtraProduct;
    }

    get displayAllocationButton() {
        return (
            this.currentState.lines.length &&
            ["incoming", "internal"].includes(this.record.picking_type_code)
        );
    }

    get displayCancelButton() {
        return !["done", "cancel"].includes(this.record.state);
    }

    get displayDestinationLocation() {
        return (
            this.groups.group_stock_multi_locations &&
            ["incoming", "internal"].includes(this.record.picking_type_code)
        );
    }

    get displayPutInPackButton() {
        return this.groups.group_tracking_lot && this.config.restrict_put_in_pack != "no";
    }

    get displayResultPackage() {
        return true;
    }

    get displaySourceLocation() {
        return (
            super.displaySourceLocation &&
            ["internal", "outgoing"].includes(this.record.picking_type_code)
        );
    }

    get displayReturnButton() {
        return this.resModel === "stock.picking" && this.isDone;
    }

    get operationSourceLocation() {
        if (this.record?.location_id) {
            return this.cache.getRecord("stock.location", this.record.location_id);
        }
        return false;
    }

    get useScanSourceLocation() {
        return super.useScanSourceLocation && this.config.restrict_scan_source_location;
    }

    get useScanDestinationLocation() {
        return super.useScanDestinationLocation && this.config.restrict_scan_dest_location != "no";
    }

    get displayValidateButton() {
        return true;
    }

    get highlightValidateButton() {
        if (!this.pageLines.length && !this.packageLines.length) {
            return false;
        }
        if (this._needsScanDestinationBeforeValidation()) {
            return false;
        }
        for (let line of this.pageLines) {
            line = this._getParentLine(line) || line;
            if (this._lineIsNotComplete(line)) {
                return false;
            }
        }
        for (const packageLine of this.packageLines) {
            if (this._lineIsNotComplete(packageLine)) {
                return false;
            }
        }
        return Boolean([...this.pageLines, ...this.packageLines].length);
    }

    get isDone() {
        return this.record.state === "done";
    }

    get isCancelled() {
        return this.record.state === "cancel";
    }

    lineIsFaulty(line) {
        return (
            this._useReservation &&
            line.qty_done > line.reserved_uom_qty &&
            (this.showReservedSns || !this.lineIsTracked(line))
        );
    }

    get moveIds() {
        return this.record.move_ids;
    }

    get pickingTypeId() {
        return this.cache.getRecord("stock.picking.type", this.record.picking_type_id.id);
    }

    get packageLines() {
        if (!this._moveEntirePackage() || !this.currentState.lines.length) {
            return [];
        }
        return this._getPackageLines();
    }

    get pageIsDone() {
        for (const line of this.groupedLines) {
            if (
                this._lineIsNotComplete(line) ||
                this._lineNeedsToBePacked(line) ||
                (line.product_id.tracking && !(line.lot_id || line.lot_name))
            ) {
                return false;
            }
        }
        for (const line of this.packageLines) {
            if (this._lineIsNotComplete(line)) {
                return false;
            }
        }
        return Boolean([...this.groupedLines, ...this.packageLines].length);
    }

    /**
     * Returns only the lines.
     * @returns {Array<Object>}
     */
    get pageLines() {
        let lines = super.pageLines;
        if (this._moveEntirePackage()) {
            lines = lines.filter(
                (line) => !(line.package_id && line.result_package_id && line.is_entire_pack)
            );
        }
        return this._sortLine(lines);
    }

    get previousScannedLinesByPackage() {
        if (this.lastScanned.packageId) {
            return this.currentState.lines.filter(
                (l) => l.result_package_id.id === this.lastScanned.packageId
            );
        }
        return [];
    }

    get printButtons() {
        const buttons = [
            {
                name: _t("Print Picking Operations"),
                class: "o_print_picking",
                method: "do_print_picking",
            },
            {
                name: _t("Print Delivery Slip"),
                class: "o_print_delivery_slip",
                method: "action_print_delivery_slip",
            },
            {
                name: _t("Print Labels"),
                class: "o_print_barcodes",
                method: "action_print_barcode",
            },
        ];
        if (this.groups.group_tracking_lot) {
            buttons.push({
                name: _t("Print Packages"),
                class: "o_print_packages",
                method: "action_print_packges",
            });
        }

        return buttons;
    }

    get reloadingMoveLines() {
        return this.currentState !== undefined;
    }

    async save() {
        if (this.linesToSave.length > 0) {
            await this._setUser();
        }
        return super.save();
    }

    /**
     * Return the last scanned package line (only relevant for "move entire package" operations.)
     */
    get selectedPackageLine() {
        return (
            this.lastScanned.packageId &&
            this.packageLines.find((pl) => pl.result_package_id.id == this.lastScanned.packageId)
        );
    }

    /**
     * Return previously scanned packages.
     */
    get lastScannedPackages() {
        const packages = [];
        for (let barcodeIndex = 0; barcodeIndex < this.scanHistory.length; barcodeIndex++) {
            const barcodeData = this.scanHistory[barcodeIndex];
            if (barcodeData.package) {
                packages.push(barcodeData.package);
            } else if (barcodeData.packageType && barcodeIndex === 0) {
                // Special case: if the last scanned barcode is a package type,
                // we skip it without breaking the loop because it can mean we want
                // to put in pack scanned package(s) into a new package of this type.
                continue;
            } else if (barcodeData.action) {
                continue; // Ignore action barcodes.
            } else {
                break;
            }
        }
        return packages;
    }

    get useExistingLots() {
        return this.record.use_existing_lots;
    }

    async uploadSignature({ signatureImage }) {
        const file = signatureImage.split(",")[1];

        this.ui.block();
        await this.orm.write(this.resModel, [this.resId], {
            signature: file,
        });
        this.ui.unblock();
        await this.save();
        this.trigger("refresh");
    }

    openSignatureDialog(validateAfterSignature = false) {
        const nameAndSignatureProps = {
            mode: "draw",
            displaySignatureRatio: 3,
            signatureType: "signature",
            noInputName: true,
        };
        const defaultName = this.record.partner_id?.display_name;

        const dialogProps = {
            defaultName,
            nameAndSignatureProps,
            uploadSignature: async (data) => {
                await this.uploadSignature(data);
                if (validateAfterSignature) {
                    await super._validate();
                }
            },
        };
        this.dialogService.add(SignatureDialog, dialogProps);
    }

    get shouldOpenSignatureModal() {
        const { picking_type_code: pickingTypeCode, signature } = this.record;
        return (
            pickingTypeCode === "outgoing" && !signature && this.groups.group_stock_sign_delivery
        );
    }

    _needsScanDestinationBeforeValidation() {
        if (this.config.lines_need_destination_location) {
            return this.currentState.lines.some((l) => l.wasUpdated && !l.lastScannedDestination);
        }
        return false;
    }

    async _validate() {
        if (this._needsScanDestinationBeforeValidation()) {
            return this.notification(_t("Destination location must be scanned"), {
                type: "danger",
            });
        }
        if (
            this.config.lines_need_to_be_packed &&
            this.currentState.lines.some((line) => this._lineNeedsToBePacked(line))
        ) {
            return this.notification(_t("All products need to be packed"), { type: "danger" });
        }
        await this._setUser();
        if (this.config.show_backorder_dialog) {
            // If there are some uncompleted lines, displays the backorder dialog.
            const uncompletedLines = [];
            const alreadyChecked = [];
            let atLeastOneLinePartiallyProcessed = false;
            for (let line of this.currentState.lines) {
                line = this._getParentLine(line) || line;
                if (alreadyChecked.includes(line.virtual_id)) {
                    continue;
                }
                // Keeps track of already checked lines to avoid to check multiple times grouped lines.
                alreadyChecked.push(line.virtual_id);
                let qtyDone = line.qty_done;
                if (qtyDone < line.reserved_uom_qty) {
                    // Checks if another move line shares the same move id and adds its quantity done in that case.
                    qtyDone += this.currentState.lines.reduce(
                        (additionalQtyDone, otherLine) =>
                            otherLine.product_id.id === line.product_id.id &&
                            otherLine.move_id === line.move_id &&
                            !otherLine.reserved_uom_qty
                                ? additionalQtyDone + otherLine.qty_done
                                : additionalQtyDone,
                        0
                    );
                    if (qtyDone < line.reserved_uom_qty) {
                        // Quantity done still insufficient.
                        uncompletedLines.push(line);
                    }
                }
                atLeastOneLinePartiallyProcessed = atLeastOneLinePartiallyProcessed || qtyDone > 0;
            }
            if (
                this.showBackOrderDialog &&
                atLeastOneLinePartiallyProcessed &&
                uncompletedLines.length
            ) {
                this.trigger("playSound");
                return this.dialogService.add(BackorderDialog, {
                    displayUoM: this.groups.group_uom,
                    uncompletedLines,
                    onApply: (backorderContext) => super._validate(backorderContext),
                    pickingIds: this.pickingIds,
                    backorderMode: this.config.create_backorder,
                });
            }
        } else {
            this.validateContext = {
                ...this.validateContext,
                picking_ids_not_to_backorder: this.pickingIds,
            };
        }
        if (this.shouldOpenSignatureModal) {
            this.openSignatureDialog(true);
            return;
        }
        return await super._validate();
    }

    // -------------------------------------------------------------------------
    // Private
    // -------------------------------------------------------------------------

    async _assignEmptyPackage(line, resultPackage) {
        const fieldsParams = this._convertDataToFieldsParams({ resultPackage });
        fieldsParams.dontUpdateSourceLocation = true;
        const parentLine = this._getParentLine(line);
        const targetLines = parentLine ? parentLine.lines : [line];
        for (const subline of targetLines) {
            // Assigns the result package on all sibling lines
            if (subline === line || (subline.qty_done && !subline.result_package_id)) {
                if (this.shouldSplitLine(subline)) {
                    // Subline has no package already and is only partially full,
                    // so we split off the remaining amount into a new move line
                    const newLine = await this.splitLine(subline);
                    [newLine.sortIndex, subline.sortIndex] = [subline.sortIndex, newLine.sortIndex];
                    if (subline === line) {
                        this.selectLine(newLine);
                    }
                }
                await this.updateLine(subline, fieldsParams);
            }
        }
    }

    _getNewLineDefaultContext() {
        return {
            default_company_id: this.record.company_id,
            default_location_id: this.lastScanned.sourceLocation.id || this._defaultLocation().id,
            default_location_dest_id: this._defaultDestLocation().id,
            default_picking_id: this.resId,
            default_qty_done: 1,
            display_default_code: false,
            hide_unlink_button: Boolean(!this.selectedLine || this.selectedLine.reserved_uom_qty),
            force_fullfil_quantity: this.selectedLine && this.selectedLine.reserved_uom_qty,
            candidatePickingsToBatch: this.candidatePickingsToBatch,
            display_name: this.record.name,
        };
    }

    async _cancel() {
        await this.save();
        await this.orm.call(this.resModel, "action_cancel", [[this.resId]]);
        this._cancelNotification();
        this.trigger("history-back");
    }

    _cancelNotification() {
        this.notification(_t("The transfer has been cancelled"));
    }

    _checkBarcode(barcodeData) {
        const check = { title: _t("Not the expected scan") };
        const { location, lot, product, destLocation, packageType } = barcodeData;
        const resultPackage = barcodeData.package;

        if (this.config.restrict_scan_source_location && !barcodeData.location) {
            // Special case where the user can not scan a destination but a source was already scanned.
            // That means what is supposed to be a destination is in this case a source.
            if (
                this.lastScanned.sourceLocation &&
                barcodeData.destLocation &&
                this.config.restrict_scan_dest_location == "no"
            ) {
                barcodeData.location = barcodeData.destLocation;
                delete barcodeData.destLocation;
            }
            // Special case where the source is mandatory and the app's waiting for but none was
            // scanned, get the previous scanned one if possible.
            if (!this.lastScanned.sourceLocation && this._currentLocation) {
                this.lastScanned.sourceLocation = this._currentLocation;
            }
        }

        if (
            this.config.restrict_scan_source_location &&
            !this._currentLocation &&
            !this.selectedLine
        ) {
            // Source Location.
            if (!location) {
                check.title = _t("Mandatory Source Location");
                check.message = _t(
                    "You are supposed to scan %s or another source location",
                    this.location.display_name
                );
            }
        } else if (this._mustScanProductFirst(barcodeData)) {
            check.message = lot
                ? _t("Scan a product before scanning a tracking number")
                : _t("You must scan a product");
        } else if (
            this.config.restrict_put_in_pack == "mandatory" &&
            !(resultPackage || packageType) &&
            this.selectedLine &&
            !this.qty_done &&
            !this.selectedLine.result_package_id &&
            ((product && product.id != this.selectedLine.product_id.id) || location || destLocation)
        ) {
            // Package.
            check.message = _t("You must scan a package or put in pack");
        } else if (
            this.config.restrict_scan_dest_location == "mandatory" &&
            !this.lastScanned.destLocation
        ) {
            // Destination Location.
            if (destLocation) {
                this.lastScanned.destLocation = destLocation;
            } else if (
                product &&
                this.selectedLine &&
                this.selectedLine.product_id.id != product.id
            ) {
                // Cannot scan another product before a destination was scanned.
                check.title = _t("Mandatory Destination Location");
                check.message = _t(
                    "Please scan destination location for %s before scanning other product",
                    this.selectedLine.product_id.display_name
                );
            }
        }
        check.error = Boolean(check.message);
        return check;
    }

    _mustScanProductFirst(barcodeData) {
        if (!this.config.restrict_scan_product) {
            return false; // No restriction setting on the product.
        }
        const { location, product } = barcodeData;
        const recPackage = barcodeData.package;
        const packageType = barcodeData.packageType || recPackage?.package_type_id;
        const packageWithQuant = recPackage?.contained_quant_ids?.length;
        const productOrPackageWasScanned = product || packageWithQuant || this.selectedLine;
        // Maybe the user scanned the wrong location and is scaning the right one.
        const rescanLocationOnRestrict =
            this.config.restrict_scan_source_location && location && !this.selectedLine;
        if (productOrPackageWasScanned || rescanLocationOnRestrict) {
            return false;
        }
        // Maybe some products were already scanned but the operation was closed
        // and reopen in the meantime, meaning no line is selected.
        if (recPackage || packageType) {
            const { linesToPack, packedLinesToPack } = this._getCandidateLinesToPack(
                packageType?.id
            );
            if (linesToPack.length || packedLinesToPack.length) {
                return false;
            }
        }
        return true;
    }

    async _closeValidate(ev) {
        const record = await this.orm.read(this.resModel, [this.record.id], ["state"]);
        if (record[0].state === "done") {
            // Checks if the picking generated a backorder. Updates the picking's data if it's the case.
            const backorders = await this.orm.searchRead(
                this.backorderModel,
                this.backordersDomain,
                ["display_name", "id"]
            );
            const buttons = backorders.map((bo) => {
                const additionalContext = { active_id: bo.id };
                return {
                    name: bo.display_name,
                    onClick: () => {
                        this.action.doAction(this.actionName, { additionalContext });
                    },
                };
            });
            if (backorders.length) {
                const phrase =
                    backorders.length === 1
                        ? _t("Following backorder was created:")
                        : _t("Following backorders were created:");
                this.validateMessage = markup`<div>
                    <p>${this.validateMessage}<br>${phrase}</p>
                </div>`;
            }
            // If all is OK, displays a notification and goes back to the previous page.
            this.notification(this.validateMessage, { type: "success", buttons });
            this.trigger("history-back");
        }
    }

    _convertDataToFieldsParams(args) {
        const params = {
            lot_name: args.lotName,
            product_id: args.product,
            qty_done: args.quantity,
        };
        if (args.lot) {
            params.lot_id = args.lot;
        }
        if (args.package) {
            params.package_id = args.package;
        }
        if (
            args.packaging &&
            args.product.tracking === "serial" &&
            (this.useExistingLots || this.canCreateNewLot)
        ) {
            params.packaging = args.packaging;
            params.qty_done = 0;
        }
        if (args.resultPackage) {
            params.result_package_id = args.resultPackage;
        }
        if (args.owner) {
            params.owner_id = args.owner;
        }
        if (args.destLocation) {
            params.location_dest_id = args.destLocation.id;
        }
        if (args.srcLocation) {
            params.location_id = args.srcLocation;
        }
        if (args.isEntirePack) {
            params.is_entire_pack = args.isEntirePack;
        }
        return params;
    }

    _createCommandVals(line) {
        const values = {
            dummy_id: line.virtual_id,
            is_entire_pack: line.is_entire_pack,
            location_id: line.location_id,
            location_dest_id: line.location_dest_id,
            lot_name: line.lot_name,
            lot_id: line.lot_id,
            outermost_result_package_id: line.outermost_result_package_id,
            owner_id: line.owner_id,
            package_id: line.package_id,
            picking_id: line.picking_id,
            picked: true,
            product_id: line.product_id,
            uom_id: line.uom_id,
            quantity: line.qty_done,
            result_package_id: line.result_package_id,
            state: "assigned",
        };
        for (const [key, value] of Object.entries(values)) {
            values[key] = this._fieldToValue(value);
        }
        return values;
    }

    _getMoveLineData(id) {
        const smlData = this.cache.getRecord("stock.move.line", id);
        smlData.dummy_id = smlData.dummy_id && Number(smlData.dummy_id);
        // Checks if this line is already in the picking's state to get back
        // its `virtual_id` (and so, avoid to set a new `virtual_id`).
        let prevLine = this.currentState?.lines.find((line) => line.id === id);
        if (!prevLine && smlData.dummy_id) {
            prevLine = this.currentState?.lines.find(
                (line) => line.virtual_id === smlData.dummy_id
            );
        }
        const previousVirtualId = prevLine && prevLine.virtual_id;
        smlData.virtual_id = smlData.dummy_id || previousVirtualId || this._uniqueVirtualId;
        smlData.product_id = this.cache.getRecord("product.product", smlData.product_id);
        smlData.uom_id = this.cache.getRecord("uom.uom", smlData.uom_id);
        smlData.packaging_uom_id =
            smlData.packaging_uom_id && this.cache.getRecord("uom.uom", smlData.packaging_uom_id);
        smlData.location_id = this.cache.getRecord("stock.location", smlData.location_id);
        smlData.location_dest_id = this.cache.getRecord("stock.location", smlData.location_dest_id);
        smlData.lot_id = smlData.lot_id && this.cache.getRecord("stock.lot", smlData.lot_id);
        smlData.owner_id =
            smlData.owner_id && this.cache.getRecord("res.partner", smlData.owner_id);
        smlData.package_id =
            smlData.package_id && this.cache.getRecord("stock.package", smlData.package_id);
        smlData.outermost_result_package_id =
            smlData.outermost_result_package_id &&
            this.cache.getRecord("stock.package", smlData.outermost_result_package_id);

        if (smlData.package_id?.parent_package_id) {
            smlData.package_id.parent_package_id = this.cache.getRecord(
                "stock.package",
                smlData.package_id.parent_package_id
            );
        }

        if (this.reloadingMoveLines) {
            if (prevLine) {
                smlData.sortIndex = prevLine.sortIndex;
                if (smlData.quantity && !smlData.qty_done) {
                    // The reservation likely changed.
                    smlData.reserved_uom_qty = smlData.quantity;
                } else {
                    if (smlData.uom_id.id !== prevLine.uom_id.id) {
                        // Compatible but not the same UoM => Need a conversion.
                        const baseQty =
                            (prevLine.reserved_uom_qty * prevLine.uom_id.factor) /
                            smlData.uom_id.factor;
                        smlData.reserved_uom_qty = this._parseFloat(baseQty);
                    } else {
                        // The reservation of this line is already known.
                        smlData.reserved_uom_qty = prevLine.reserved_uom_qty;
                    }
                }
            } else {
                // This line was created in the Barcode App, so it has no reservation.
                smlData.qty_done = smlData.quantity;
                smlData.reserved_uom_qty = 0;
            }
        } else {
            // First loading: `reserved_uom_qty` keeps in memory what is the
            // initial reservation for this move line clientside only, this
            // information is lost once the user closes the operation.
            smlData.reserved_uom_qty = smlData.quantity;
        }

        const resultPackage =
            smlData.result_package_id &&
            this.cache.getRecord("stock.package", smlData.result_package_id);
        if (resultPackage) {
            // Fetch the package type if needed.
            smlData.result_package_id = resultPackage;
            const packageType = resultPackage && resultPackage.package_type_id;
            resultPackage.package_type_id =
                packageType && this.cache.getRecord("stock.package.type", packageType);
        }
        if (smlData.result_package_id?.parent_package_id) {
            smlData.result_package_id.parent_package_id = this.cache.getRecord(
                "stock.package",
                smlData.result_package_id.parent_package_id
            );
        }
        return smlData;
    }

    _createLinesState() {
        const lines = [];
        const picking = this.cache.getRecord(this.resModel, this.resId);
        for (const id of picking.move_line_ids) {
            const smlData = this._getMoveLineData(id);
            lines.push(smlData);
        }
        return lines;
    }

    _defaultLocation() {
        return this.cache.getRecord("stock.location", this.record.location_id);
    }

    _defaultDestLocation() {
        return this.cache.getRecord("stock.location", this.record.location_dest_id);
    }

    _defaultScrapLocation() {
        return Object.values(this.cache.dbIdCache["stock.location"]).find(
            (location) => location.usage == "inventory"
        );
    }

    /**
     * Find non-stored goods lines for a specific package.
     * @param {Object} recPackage
     * @returns {Array<Object>}
     */
    _findConsumableLinesFromPackage(recPackage) {
        return this.pageLines.filter(
            (line) =>
                line.product_id &&
                !line.product_id.is_storable &&
                line.package_id &&
                this._isPackageInPackage(line.package_id, recPackage, false)
        );
    }

    _getCommands() {
        const commands = Object.assign(super._getCommands(), {
            OBTPRSL: this.print.bind(this, false, "action_print_delivery_slip"),
            OBTPROP: this.print.bind(this, false, "do_print_picking"),
            OBTSCRA: this._scrap.bind(this),
            OBTRETU: this._returnProducts.bind(this),
        });
        if (!this.isDone) {
            commands["OBTPACK"] = this._putInPack.bind(this);
            commands["OCDCANC"] = this._cancel.bind(this);
        }
        // Dummy command to avoid error message.
        commands.OBTUPCK = () => {};
        return commands;
    }

    _getDefaultMessageType() {
        if (this.useScanSourceLocation && !this.lastScanned.sourceLocation) {
            return "scan_src";
        }
        return "scan_product";
    }

    _getModelRecord() {
        const record = this.cache.getRecord(this.resModel, this.resId);
        if (record.picking_type_id && record.state !== "cancel") {
            record.picking_type_id = this.cache.getRecord(
                "stock.picking.type",
                record.picking_type_id
            );
        }
        if (record.partner_id && record.state !== "cancel") {
            record.partner_id = this.cache.getRecord("res.partner", record.partner_id);
        }
        this.pickingIds = [this.resId];
        return record;
    }

    async _createNewLine(params) {
        const { fieldsParams } = params;
        if (fieldsParams?.lot_id && !fieldsParams.location_id && !this.lastScanned.sourceLocation) {
            const quants = (
                await this.cache.getQuants(fieldsParams.product_id, false, {
                    lot_id: fieldsParams.lot_id,
                })
            ).filter((quant) => quant.quantity > 0);
            if (quants.length === 1) {
                const quantLocation = this.cache.getRecord(
                    "stock.location",
                    quants[0].location_id,
                    false
                );
                if (quantLocation) {
                    fieldsParams.location_id = quantLocation;
                }
            }
        }
        return await super._createNewLine(params);
    }

    _getNewLineDefaultValues(fieldsParams) {
        const defaultValues = super._getNewLineDefaultValues(...arguments);
        let locationDest = this._defaultDestLocation();
        if (
            this.selectedLine &&
            !fieldsParams.move_id &&
            this.selectedLine.product_id.id === fieldsParams.product_id?.id
        ) {
            defaultValues.move_id = this.selectedLine.move_id;
            if (this._lineIsNotComplete(this.selectedLine)) {
                // still fulfilling the reserved line, so follow its destination
                locationDest = this.selectedLine.location_dest_id;
            }
        }
        const newLineDefaultVals = Object.assign(defaultValues, {
            location_dest_id: locationDest,
            reserved_uom_qty: 0,
            qty_done: 0,
            picking_id: this.resId,
            result_package_id: false,
            outermost_package_id: false,
            outermost_result_package_id: false,
            is_entire_pack: false,
        });
        if (fieldsParams.product_id?.tracking === "serial" && fieldsParams.packaging) {
            newLineDefaultVals.reserved_uom_qty = 1;
        }
        return newLineDefaultVals;
    }

    _getFieldToWrite() {
        return [
            "is_entire_pack",
            "location_id",
            "location_dest_id",
            "lot_id",
            "lot_name",
            "package_id",
            "outermost_result_package_id",
            "owner_id",
            "qty_done",
            "result_package_id",
        ];
    }

    _getPackageLines() {
        const linesWithPackage = this.currentState.lines.filter(
            (line) =>
                line.is_entire_pack &&
                line.package_id &&
                line.result_package_id &&
                line.package_id.complete_name === line.result_package_id.complete_name
        );
        // Groups lines by package.
        const groupedLines = {};
        for (const line of linesWithPackage) {
            const upperSourcePackageId = line.package_id.parent_package_id
                ? line.package_id.parent_package_id.id
                : line.package_id.id;
            const upperDestPackageId =
                line.outermost_result_package_id.id || line.result_package_id.id;
            const groupKey =
                upperSourcePackageId === upperDestPackageId
                    ? `${upperSourcePackageId}_${upperDestPackageId}`
                    : `${line.package_id.id}_${line.result_package_id.id}`;
            if (!groupedLines[groupKey]) {
                groupedLines[groupKey] = [];
            }
            groupedLines[groupKey].push(line);
        }
        const packageLines = [];
        for (const key in groupedLines) {
            // Check if the package is reserved.
            const reservedPackage = groupedLines[key].every((line) => this.lineIsReserved(line));
            const packageLine = Object.assign({}, groupedLines[key][0], {
                lines: groupedLines[key],
                isPackageLine: true,
                reservedPackage,
            });
            packageLines.push(packageLine);
        }
        return this._sortLine(packageLines);
    }

    _getSaveCommand() {
        const commands = this._getSaveLineCommand();
        if (commands.length) {
            return {
                route: "/stock_barcode/save_barcode_data",
                params: {
                    model: this.resModel,
                    res_id: this.resId,
                    write_field: "move_line_ids",
                    write_vals: commands,
                },
            };
        }
        return {};
    }

    _getScanPackageMessage() {
        return _t("Scan a package or put in pack");
    }

    _groupSublines() {
        const groupedLine = super._groupSublines(...arguments);
        let [sumQtyDemand, sumQtyDone] = [0, 0];
        const groupedFactor = groupedLine.uom_id.factor;
        for (const subline of groupedLine.lines) {
            sumQtyDemand += (this.getQtyDemand(subline) * subline.uom_id.factor) / groupedFactor;
            sumQtyDone += (this.getQtyDone(subline) * subline.uom_id.factor) / groupedFactor;
        }
        groupedLine.reserved_uom_qty = this._parseFloat(sumQtyDemand);
        groupedLine.qty_done = this._parseFloat(sumQtyDone);
        return groupedLine;
    }

    _incrementTrackedLine() {
        return !(this.record.use_create_lots || this.record.use_existing_lots);
    }

    _lineCannotBeTaken(line) {
        // A packed line without expected quantity or completed cannot be taken
        const fullyPacked =
            line.result_package_id && (!line.reserved_uom_qty || this._lineIsComplete(line));
        return fullyPacked || super._lineCannotBeTaken(...arguments);
    }

    _lineIsComplete(line) {
        const isComplete = line.reserved_uom_qty && line.qty_done >= line.reserved_uom_qty;
        if (line.isPackageLine && !line.reserved_uom_qty && line.qty_done) {
            return true; // For package line, considers an unreserved package as a completed line.
        }
        if (isComplete && line.lines) {
            // Grouped lines/package lines have multiple sublines.
            for (const subline of line.lines) {
                // For tracked product, a line with `qty_done` but no tracking number is considered as not complete.
                if (subline.product_id.tracking) {
                    if (subline.qty_done && !(subline.lot_id || subline.lot_name)) {
                        return false;
                    }
                } else if (
                    subline.reserved_uom_qty &&
                    subline.qty_done < subline.reserved_uom_qty
                ) {
                    return false;
                }
            }
        }
        return isComplete;
    }

    _lineIsNotComplete(line) {
        const currentLine =
            (["lot", "serial"].includes(line.product_id.tracking) && this._getParentLine(line)) ||
            line;
        let isNotComplete =
            currentLine.reserved_uom_qty && currentLine.qty_done < currentLine.reserved_uom_qty;
        // if we're using the parent line we don't want to return true if the parent line is incomplete but not the line
        if (isNotComplete && line != currentLine) {
            isNotComplete = line.reserved_uom_qty && line.qty_done < line.reserved_uom_qty;
        }
        if (!isNotComplete && currentLine.lines) {
            // Grouped lines/package lines have multiple sublines.
            for (const subline of currentLine.lines) {
                // For tracked product, a line with `qty_done` but no tracking number is considered as not complete.
                if (subline.product_id.tracking) {
                    if (subline.qty_done && !(subline.lot_id || subline.lot_name)) {
                        return true;
                    }
                } else if (
                    subline.reserved_uom_qty &&
                    subline.qty_done < subline.reserved_uom_qty
                ) {
                    return true;
                }
            }
        }
        return isNotComplete;
    }

    _lineNeedsToBePacked(line) {
        return Boolean(
            this.config.lines_need_to_be_packed && line.qty_done && !line.result_package_id
        );
    }

    _moveEntirePackage() {
        return this.record.picking_type_entire_packs;
    }

    async _processBarcode(barcode) {
        if (barcode.startsWith("OBTRETU:")) {
            const barcodeParts = barcode.split(":");
            this.barcodeReturnReason = barcodeParts[1];
            // Forward only the original OBTRETU command
            barcode = "OBTRETU";
        }
        if (this.isDone && !this.commands[barcode]) {
            return this.notification(_t("This picking is already done"), { type: "danger" });
        }
        return super._processBarcode(barcode);
    }

    async _processLocation(barcodeData) {
        super._processLocation(...arguments);
        if (barcodeData.destLocation) {
            await this._processLocationDestination(barcodeData);
            this.trigger("update");
        }
    }

    async _processLocationSource(barcodeData) {
        // For planned transfers, check the scanned location is a part of transfer source location.
        const linesLocationIds = this.currentState.lines.map((line) => line.location_id.id);
        if (
            this._useReservation &&
            !this._isSublocation(barcodeData.location, this._defaultLocation()) &&
            !linesLocationIds.includes(barcodeData.location.id)
        ) {
            barcodeData.stopped = true;
            const message = _t("The scanned location doesn't belong to this operation's location");
            return this.notification(message, { type: "danger" });
        }
        super._processLocationSource(...arguments);
        // Splits uncompleted lines to be able to add reserved products from unreserved location.
        let currentLine = this.selectedLine || this.lastScannedLine;
        currentLine = this._getParentLine(currentLine) || currentLine;
        if (currentLine && currentLine.location_id.id !== barcodeData.location.id) {
            const qtyDone = this.getQtyDone(currentLine);
            const reservedQty = this.getQtyDemand(currentLine);
            const remainingQty = reservedQty - qtyDone;
            if (this.shouldSplitLine(currentLine)) {
                const fieldsParams = this._convertDataToFieldsParams(barcodeData);
                let newLine;
                if (currentLine.lines) {
                    for (const line of currentLine.lines) {
                        if (!line.reserved_uom_qty) {
                            line.reserved_uom_qty = line.qty_done;
                        }
                        if (this.shouldSplitLine(line) && !newLine) {
                            newLine = await this._createNewLine({
                                copyOf: line,
                                fieldsParams,
                            });
                            delete newLine.parentLine;
                            line.reserved_uom_qty = line.qty_done;
                        }
                    }
                } else {
                    newLine = await this._createNewLine({
                        copyOf: currentLine,
                        fieldsParams,
                    });
                }
                currentLine.reserved_uom_qty = qtyDone;
                if (newLine) {
                    newLine.reserved_uom_qty = remainingQty;
                    newLine.lot_id = false;
                    this._markLineAsDirty(newLine);
                }
                this._markLineAsDirty(currentLine);
            }
        }
    }

    /**
     * Returns true if the first given location is a sublocation of the second given location.
     * @param {Object} childLocation
     * @param {Object} parentLocation
     * @returns {boolean}
     */
    _isSublocation(childLocation, parentLocation) {
        return childLocation.parent_path.indexOf(parentLocation.parent_path) === 0;
    }

    /**
     * Returns true if the package has an acceptable location to be processed.
     * @param {Boolean} hasConsuLines
     * @param {Object} packLocation
     * @param {Object} srcLocation
     */
    _isPackLocationValid(hasConsuLines, packLocation, srcLocation) {
        if (!packLocation && hasConsuLines) {
            // If package only has consumables inside, it'll have no location but remain valid.
            return true;
        }
        // Package needs to be at the source location to add its content
        return !srcLocation || (packLocation && this._isSublocation(packLocation, srcLocation));
    }

    _getLinesToMove() {
        const configScanDest = this.config.restrict_scan_dest_location;
        // Usually, assign the destination to the selected line or to the selected package's lines.
        let lines = this.selectedLine ? [this.selectedLine] : [];
        if (this.selectedPackageLine?.lines) {
            lines = this.selectedPackageLine.lines;
        }
        if (
            configScanDest === "mandatory" &&
            ["lot", "serial"].includes(this.selectedLine?.product_id?.tracking)
        ) {
            // When we assign the location to only the last scanned line, if the selected line is
            // tracked, we want to assign the destination to its scanned sibling lines too.
            const parentLine = this._getParentLine(this.selectedLine);
            if (parentLine) {
                lines = this.previousScannedLines.filter((line) =>
                    parentLine.virtual_ids.includes(line.virtual_id)
                );
            }
        } else if (configScanDest === "optional" && this.previousScannedLines?.length) {
            // If config is "After group of Products", get all previously scanned lines.
            for (const line of this.previousScannedLines) {
                if (!lines.find((l) => l.virtual_id === line.virtual_id)) {
                    lines.push(line);
                }
            }
        }
        if (this.previousScannedLinesByPackage?.length) {
            // In case some lines were added by scanning a package, get those lines.
            lines.push(...this.previousScannedLinesByPackage);
        }

        return Array.from(new Set(lines));
    }

    _getLineMoveId(line) {
        return line.move_id;
    }

    async beforeQuit() {
        await super.beforeQuit();
        await this._onExit();
    }

    _convertQuantity(quantity, fromUom, toUom) {
        if (!quantity || fromUom.factor === toUom.factor) {
            return quantity;
        }
        return this._parseFloat((quantity * fromUom.factor) / toUom.factor);
    }

    _onExit() {
        if (["done", "cancel"].includes(this.record.state) || this.moveIds?.length === 0) {
            // No need to all post process if operation is closed or have no move.
            return;
        }
        const quantitiesByMove = this.initialState.lines.reduce((res, line) => {
            const moveId = this._getLineMoveId(line);
            const move = this.cache.getRecord("stock.move", moveId);
            const moveUom = this.cache.getRecord("uom.uom", move.uom_id);
            if (!res[moveId]) {
                res[moveId] = { quantity_done: 0, reserved_uom_qty: 0 };
            }
            res[moveId].quantity_done += this._convertQuantity(line.qty_done, line.uom_id, moveUom);
            res[moveId].reserved_uom_qty += this._convertQuantity(
                line.reserved_uom_qty,
                line.uom_id,
                moveUom
            );

            return res;
        }, {});
        return this.orm.call("stock.move", "post_barcode_process", [
            this.moveIds,
            quantitiesByMove,
        ]);
    }

    async onPrintReservation(line) {
        const reportAction = (
            await this.orm.searchRead("ir.actions.report", [
                ["report_name", "=", "stock.report_reception_report_label"],
            ])
        )[0];
        const docids = [line.move_id];
        const data = { docids, quantity: String(this.getQtyDemand(line)) };
        const context = { active_ids: docids };
        return this.action.doAction({ ...reportAction, context, data });
    }

    async _processLocationDestination(barcodeData) {
        const configScanDest = this.config.restrict_scan_dest_location;
        if (configScanDest == "no") {
            return;
        }
        // For planned transfers, check the scanned location is a part of transfer destination.
        if (
            this._useReservation &&
            !this._isSublocation(barcodeData.destLocation, this._defaultDestLocation())
        ) {
            barcodeData.stopped = true;
            const message = _t(
                "The scanned location doesn't belong to this operation's destination"
            );
            return this.notification(message, { type: "danger" });
        }

        // Change the destination of all concerned lines.
        const lines = this._getLinesToMove();
        for (const line of lines) {
            await this.changeDestinationLocation(barcodeData.destLocation.id, line);
        }
        barcodeData.stopped = true;
    }

    async _processPackage(barcodeData) {
        const { packageName } = barcodeData;
        const recPackage = barcodeData.package;
        if (barcodeData.packageType && !recPackage) {
            // Scanned a package type and no existing package: make a put in pack (forced package type).
            barcodeData.stopped = true;
            return await this._processPackageType(barcodeData);
        } else if (packageName && !recPackage) {
            // Scanned a non-existing package: make a put in pack.
            this.lastScanned.packageId = false;
            barcodeData.stopped = true;
            return await this._putInPack({ default_name: packageName });
        } else if (!recPackage) {
            return; // No package, package's type or package's name => Nothing to do.
        }
        const packLocation = recPackage.location_id
            ? this.cache.dbIdCache["stock.location"][recPackage.location_id]
            : false;
        if (recPackage.location_id && !packLocation) {
            // The package is in a location but the location was not found in the cache,
            // surely because this location is not related to this picking.
            return;
        }
        if (
            packLocation &&
            packLocation.id !== this._defaultDestLocation().id &&
            ((this.config.restrict_scan_source_location && packLocation.id !== this.location.id) ||
                (!this.config.restrict_scan_source_location &&
                    !this._isSublocation(packLocation, this.location)))
        ) {
            // Package is not located at the destination (result package) and is not located at the
            // scanned source location (or one of its sublocations) neither.
            return;
        }

        let alreadyDonePackId;
        let scannedPackages = false;
        let validatedLines = false;
        for (const packageLine of this.packageLines) {
            if (!this._isPackageInPackage(packageLine.package_id, recPackage)) {
                continue;
            }
            // Scanned package is either a parent of a line package or the package itself,
            // thus need to validate all relevant lines.
            if (packageLine.qty_done) {
                alreadyDonePackId = recPackage.id;
                continue;
            }
            for (const line of packageLine.lines) {
                this.selectedLineVirtualId = line.virtual_id;
                await this._updateLineQty(line, { qty_done: line.reserved_uom_qty });
                this._markLineAsDirty(line);
                scannedPackages = true;
            }
        }
        if (this.record.picking_type_code === "incoming") {
            // For receipts, we can scan a destination package to validate all its corresponding lines.
            for (const line of this.pageLines) {
                if (
                    line.result_package_id &&
                    this._isPackageInPackage(line.result_package_id, recPackage) &&
                    this._lineIsNotComplete(line)
                ) {
                    const fieldsParams = this._convertDataToFieldsParams({
                        quantity: line.reserved_uom_qty - line.qty_done,
                    });
                    await this.updateLine(line, fieldsParams);
                    validatedLines = true;
                }
            }
        }
        if (alreadyDonePackId && !scannedPackages && !validatedLines) {
            this.lastScanned.packageId = alreadyDonePackId;
            this.notification(_t("This package is already scanned."), { type: "danger" });
        }
        if (scannedPackages || validatedLines || alreadyDonePackId) {
            this.lastScanned.packageId = recPackage.id;
            barcodeData.stopped = true;
            return this.trigger("update");
        }

        // Scanned a package: fetches package's quant and creates a line for
        // each of them, except if the package is already scanned.
        // TODO: can check if quants already in cache to avoid to make a RPC if
        // there is all in it (or make the RPC only on missing quants).
        let currentSelectedPackageLine = false;
        if (this.lastScanned.packageId) {
            currentSelectedPackageLine = this.selectedPackageLine;
            this.lastScanned.packageId = false;
        }
        let quants = [];
        if (recPackage.contained_quant_ids.length) {
            const res = await this.orm.call("stock.quant", "get_stock_barcode_data_records", [
                recPackage.contained_quant_ids,
            ]);
            this.cache.setCache(res.records);
            quants = res.records["stock.quant"];
        }
        // If the package is empty or is already at the destination location,
        // assign it to the last scanned line.
        const currentLine = currentSelectedPackageLine || this.selectedLine || this.lastScannedLine;
        if (this.lineCanBePackedIntoPackage(currentLine, recPackage)) {
            const linesToUpdate = [currentLine];
            if (this.config.restrict_put_in_pack === "optional") {
                // If the current line is not packed yet, we want to pack only unpacked lines,
                // but if the current line is packed, we want to pack only the lines who are
                // already packed but where the package isn't itself in another package.
                const filterFunction = !currentLine.result_package_id
                    ? (line) => !line.result_package_id
                    : (line) => line.result_package_id && !line.result_package_id.package_dest_id;
                linesToUpdate.push(
                    ...this.previousScannedLines.filter(
                        (line) =>
                            line.qty_done &&
                            line.virtual_id !== currentLine.virtual_id &&
                            filterFunction(line)
                    )
                );
            }
            if (!currentLine.result_package_id) {
                for (const line of linesToUpdate) {
                    await this._assignEmptyPackage(line, recPackage);
                }
            } else {
                const packageIds = linesToUpdate.map((l) => l.result_package_id?.id);
                await this._putPackInPack(packageIds, {
                    default_package_id: recPackage.id,
                });
            }
            barcodeData.stopped = true;
            this.lastScanned.packageId = recPackage.id;
            this.trigger("update");
            return;
        } else if (!currentLine && this.previousScannedLines.length === 0) {
            const packageTypeId = recPackage.package_type_id?.id;
            const additionalParams = {
                default_package_id: recPackage.id,
                default_package_type_id: packageTypeId,
            };
            const linesWerePacked = await this._packUnscannedLines(additionalParams);
            if (linesWerePacked) {
                barcodeData.stopped = true;
                return;
            }
        }

        // Do not allow extra products if they are not allowed
        if (!this._allowExtraProduct) {
            const allowedProductIds = new Set(
                this.currentState.lines.map((line) => line.product_id.id)
            );
            if (quants.some((quant) => !allowedProductIds.has(quant.product_id))) {
                barcodeData.error = _t(
                    "This package contains extra products and extra products are not allowed on this operation."
                );
                return;
            }
        }

        // Pick all consumable-product lines from the same package
        const consuLines = this._findConsumableLinesFromPackage(recPackage);
        if (!this._isPackLocationValid(!!consuLines.length, packLocation, this.location)) {
            return;
        }

        // Checks if the package is already scanned.
        let alreadyExisting = 0;
        for (const line of this.pageLines) {
            const samePackage = line.package_id?.id === recPackage.id;
            const sameContainer = line.package_id?.parent_package_id?.id === recPackage.id;
            if ((samePackage || sameContainer) && this.getQtyDone(line) > 0) {
                alreadyExisting++;
            }
        }
        if (alreadyExisting >= quants.length + consuLines.length) {
            barcodeData.error = _t("This package is already scanned.");
            return;
        } else if (alreadyExisting) {
            const userConfirmation = Promise.withResolvers();
            this.dialogService.add(ConfirmationDialog, {
                body: _t(
                    "You have already scanned %s items of this package. Do you want to scan the whole package?",
                    alreadyExisting
                ),
                title: _t("Scanning package"),
                cancel: () => userConfirmation.resolve(false),
                confirm: () => userConfirmation.resolve(true),
                close: () => userConfirmation.resolve(false),
            });
            if (!(await userConfirmation.promise)) {
                barcodeData.stopped = true;
                return;
            }
        }

        // For each quants, creates or increments a barcode line.
        for (const quant of quants) {
            const quantUoM = this.cache.getRecord("uom.uom", quant.uom_id);
            const product = this.cache.getRecord("product.product", quant.product_id);
            const quantPackage = this.cache.getRecord("stock.package", quant.package_id);
            const searchLineParams = Object.assign({}, barcodeData, { product, quantPackage });
            let remaining_qty = quant.quantity;
            let qty_used = 0;
            while (remaining_qty > 0) {
                const currentLine = this._findLine(searchLineParams);
                if (currentLine) {
                    // Updates an existing line.
                    const uomFactor = quantUoM.factor / currentLine.uom_id.factor;
                    const lineQtyDiff = currentLine.reserved_uom_qty - currentLine.qty_done;
                    const qtyNeeded = Math.max(lineQtyDiff, 0) / uomFactor;
                    qty_used = qtyNeeded ? Math.min(qtyNeeded, remaining_qty) : remaining_qty;
                    const fieldsParams = this._convertDataToFieldsParams({
                        quantity: qty_used * uomFactor,
                        lotName: barcodeData.lotName,
                        lot: barcodeData.lot,
                        package: quant.package_id,
                        owner: barcodeData.owner,
                    });
                    await this.updateLine(currentLine, fieldsParams);
                } else {
                    // Creates a new line.
                    qty_used = this._parseFloat(remaining_qty);
                    const isEntirePack = qty_used === quant.quantity;
                    const fieldsParams = this._convertDataToFieldsParams({
                        product,
                        quantity: qty_used,
                        lot: quant.lot_id,
                        package: quant.package_id,
                        resultPackage: quant.package_id,
                        owner: quant.owner_id,
                        srcLocation: quant.location_id,
                        isEntirePack,
                    });
                    if (quant.package_id !== recPackage.id) {
                        fieldsParams.outermost_result_package_id = recPackage;
                    }
                    const newLine = await this._createNewLine({ fieldsParams });
                    if (isEntirePack) {
                        // Keep in memory what was the initial package line's quantity.
                        newLine.packedQuantity = qty_used;
                    }
                }
                remaining_qty -= qty_used;
            }
        }

        for (const line of consuLines) {
            if (!this._lineIsNotComplete(line)) {
                continue;
            }
            const fieldsParams = this._convertDataToFieldsParams({
                quantity: line.reserved_uom_qty - line.qty_done,
            });
            await this.updateLine(line, fieldsParams);
        }

        barcodeData.stopped = true;
        this.selectedLineVirtualId = false;
        this.lastScanned.packageId = recPackage.id;
        this.trigger("update");
    }

    async _packUnscannedLines(additionalParams) {
        if (this.previousScannedLines.length === 0) {
            // In case no scan was done yet, check if we can pack already
            // processed lines (eg.: reopening an already started operation.)
            const packageTypeId = additionalParams.default_package_type_id;
            const { linesToPack, packedLinesToPack } = this._getCandidateLinesToPack(packageTypeId);
            if (!packedLinesToPack.length && linesToPack.length) {
                // We have some lines waiting for a package => Do a put in pack.
                await this._putInPack(additionalParams);
                return true;
            } else if (packedLinesToPack.length) {
                // We only have packed lines waiting for a container => Do a pack in pack.
                const packageToPackIds = packedLinesToPack.map((l) => l.result_package_id.id);
                await this._putPackInPack(packageToPackIds, additionalParams);
                return true;
            }
        }
        return false;
    }

    async _processPackageType(barcodeData) {
        const { packageType } = barcodeData;
        if (!this.selectedLine && this.lastScannedPackages.length && packageType) {
            // One or multiple packages were previously scanned and a package
            // type is now scanned => Put the scanned package(s) in a new package.
            const scannedPackageIds = this.lastScannedPackages.map((pack) => pack.id);
            const packageIds = new Set();
            for (const packageId of scannedPackageIds) {
                const packageLines = this.currentState.lines.filter(
                    (line) =>
                        line.package_id &&
                        (line.result_package_id?.id === packageId ||
                            line.result_package_id?.parent_package_id?.id === packageId)
                );
                for (const packageLine of packageLines) {
                    packageIds.add(packageLine.package_id.id);
                }
                // For receipts, we can scan a destination package to validate all its corresponding lines.
                // So in this case, we need to check the result packages instead
                if (this.record.picking_type_code === "incoming") {
                    const receiptPackageLines = this.currentState.lines.filter(
                        (line) =>
                            !line.package_id &&
                            (line.result_package_id?.id == packageId ||
                                line.result_package_id?.package_dest_id?.id == packageId)
                    );
                    for (const packageLine of receiptPackageLines) {
                        packageIds.add(packageLine.result_package_id.id);
                    }
                }
            }
            if (packageIds?.size) {
                return await this._putPackInPack(Array.from(packageIds), {
                    default_package_type_id: packageType.id,
                    default_name: barcodeData?.packageName,
                });
            }
            if (this.lastScannedPackages.length) {
                const scannedPackageIds = this.lastScannedPackages.map((pack) => pack.id);
                const hasLinesToPack = this.currentState.lines.some(
                    (line) =>
                        scannedPackageIds.includes(line.package_id?.id) &&
                        line.qty_done &&
                        !line.result_package_id
                );
                if (hasLinesToPack) {
                    const additionalParams = { default_package_type_id: packageType.id };
                    if (barcodeData.packageName) {
                        additionalParams.default_name = barcodeData.packageName;
                    }
                    return await this._putInPack(additionalParams);
                }
            }
        }
        if (this.mustTryPackUnscannedLine()) {
            barcodeData.stopped = true;
            const additionalParams = {
                default_name: barcodeData?.packageName,
                default_package_type_id: packageType.id,
            };
            const linesWerePacked = await this._packUnscannedLines(additionalParams);
            const message = _t(
                "You can't apply a package type. First, scan product or select a line"
            );
            return linesWerePacked || this.notification(message, { type: "warning" });
        }
        const resultPackage =
            this.selectedLine?.outermost_result_package_id || this.selectedLine?.result_package_id;
        if (!resultPackage) {
            // No package on the line => Do a put in pack.
            const additionalParams = { default_package_type_id: packageType.id };
            if (barcodeData.packageName) {
                additionalParams.default_name = barcodeData.packageName;
            }
            return await this._putInPack(additionalParams);
        } else if (!resultPackage.package_type_id) {
            // Changes the package type for the scanned one.
            await this.save();
            await this.orm.write("stock.package", [resultPackage.id], {
                package_type_id: packageType.id,
            });
            const message = _t("Package type %(type)s applied to the package %(package)s", {
                type: packageType.name,
                package: resultPackage.name,
            });
            this.notification(message, { type: "success" });
            return this.trigger("refresh");
        } else {
            // Put package(s) inside a new one of the scanned package type.
            const packageToPackIds = this.getPackageToPackIds();
            return this._putPackInPack(packageToPackIds, {
                default_package_type_id: packageType.id,
                default_name: barcodeData?.packageName,
            });
        }
    }

    /**
     * This method is useful to know if some lines can be packed when there is no scan history.
     * Usually, we do operation on last scanned products, but in case of put
     * in pack, it can be done once some lines have quantity done even if no
     * scan was made (eg.: operation is re-opened after interruption.)
     *
     * @param {number} [packageTypeId] - A packed line can not be packed into a
     * package of the same type. In case the package has a type or a package
     * type was scanned, it's important to give the package type ID to exclude
     * already packed line sharing the same package type.
     * @returns {Object} Two keys: `linesToPack` (lines without result package)
     * and `packedLinesToPack` (lines already packed.)
     */
    _getCandidateLinesToPack(packageTypeId = false) {
        let [linesToPack, packedLinesToPack] = [[], []];
        const currentLine = this.selectedLine || this.lastScannedLine;
        if (!currentLine && this.previousScannedLines.length === 0) {
            // In case no scan was done yet, check if we can pack already
            // processed lines (eg.: reopening an already started operation.)
            linesToPack = this.currentState.lines.filter(
                (line) =>
                    line.qty_done &&
                    !line.outermost_result_package_id &&
                    (!line.result_package_id ||
                        !packageTypeId ||
                        line.result_package_id.package_type_id?.id !== packageTypeId)
            );
            packedLinesToPack = linesToPack.filter(
                (line) =>
                    line.result_package_id &&
                    line.result_package_id.package_type_id?.id !== packageTypeId
            );
        }
        return { linesToPack, packedLinesToPack };
    }

    /**
     * Checks whether we need to create a package for the given line. We need to do so if:
     * - The scanned packaging is linked to a package type;
     * - The line uses a different UoM;
     * - The "Units of Measure & Packagings" setting must be enabled.
     * @param {Object} currentLine
     * @param {Object} packaging
     * @returns {boolean|Object} either false or the packaging's UoM.
     */
    getPackageCreationUom(currentLine, packaging) {
        if (!this.groups.group_tracking_lot || !packaging || !packaging.uom_id) {
            return false;
        }
        const packagingUom = this.cache.getRecord("uom.uom", packaging.uom_id);
        const returnUom = packagingUom.package_type_id && packagingUom.id != currentLine.uom_id.id;
        return returnUom ? packagingUom : false;
    }

    async _putInPack(additionalParams = {}, splitLines = true) {
        const context = {
            barcode_view: true,
            avoid_putaway_rules: true,
        };
        if (this.selectedLine?.result_package_id) {
            // If selected line is already packed, we do a "pack in pack" instead of a "put in pack"
            const packageToPackIds = this.getPackageToPackIds();
            return this._putPackInPack(packageToPackIds, context);
        }
        if (!this.groups.group_tracking_lot) {
            return this.notification(_t("To use packages, enable 'Packages' in the settings"), {
                type: "danger",
            });
        }
        // Before the put in pack, create a new empty move line with the remaining
        // quantity for each uncompleted move line who will be packaged.
        if (splitLines) {
            const lines = [...this.pageLines];
            for (const line of lines) {
                if (line.result_package_id || !this.shouldSplitLine(line)) {
                    continue; // Line is already in a package or no quantity to process.
                }
                await this.splitLine(line);
            }
        }
        await this.save();
        const result = await this.orm.call(this.resModel, "action_put_in_pack", [[this.resId]], {
            ...this.getPutInPackParams(additionalParams),
            context,
        });
        if (typeof result === "object" && result.type) {
            return this.trigger("process-action", result);
        }
        this.trigger("refresh");
    }

    async _putInPackaging(line, packaging) {
        const packagingUom = this.getPackageCreationUom(line, packaging);
        if (packagingUom) {
            // If a packaging was scanned and it's linked to a package type,
            // put in pack the product's move line for the given UoM quantity.
            await this._putCapacityInPack(line, packagingUom.factor, packagingUom.package_type_id);
        }
    }

    async _putCapacityInPack(line, packageCapacity, packageTypeId) {
        if (!this.groups.group_tracking_lot) {
            return this.notification(_t("To use packages, enable 'Packages' in the settings"), {
                type: "danger",
            });
        } else if (!line || line.result_package_id) {
            return false; // No line to pack or is already packed.
        } else if (packageCapacity <= 0 || packageCapacity > line.reserved_uom_qty) {
            return false; // Wrong quantity to pack.
        }

        if (this.shouldSplitLine(line)) {
            // Move exceeding quantity to a new line.
            const newLine = await this.splitLine(line, packageCapacity);
            this._selectLine(newLine);
            this._markLineAsDirty(newLine);
        }
        // Put the line in pack.
        await this.save();
        await this.orm.call("stock.move.line", "action_put_in_pack", [[line.id]], {
            package_type_id: packageTypeId,
            context: {
                barcode_view: true,
                avoid_putaway_rules: true,
            },
        });
        this.trigger("refresh");
    }
    getPutInPackParams(params) {
        return {
            package_type_id: params.default_package_type_id,
            package_name: params.default_name,
            package_id: params.default_package_id,
        };
    }

    /**
     * Define which line must be packed, depending of the selected line.
     * If the selected line is already packed, pack other already packed lines.
     * If selected line is not packed, pack other no packed lines.
     * If selected line has some quantity, pack only lines with quantity.
     * @returns {Array<number>} list of packages' id
     */
    getPackageToPackIds() {
        const packageIds = [];
        // Define what level of packs need to be packed.
        const mustPackAlreadyPacked = Boolean(this.selectedLine.result_package_id.package_dest_id);
        const mustPackWithQuantity = Boolean(this.getQtyDone(this.selectedLine));
        let lines = this.previousScannedLines;
        if (lines.length === 0 && this.selectedLine) {
            lines = [this.selectedLine];
        }
        for (const line of lines) {
            if (mustPackAlreadyPacked && !line.result_package_id.package_dest_id) {
                continue;
            } else if (
                !mustPackAlreadyPacked &&
                (!line.result_package_id || line.result_package_id.package_dest_id)
            ) {
                continue;
            } else if (mustPackWithQuantity && !this.getQtyDone(line)) {
                continue;
            }
            packageIds.push(line.result_package_id.id);
        }
        return packageIds;
    }

    async _putPackInPack(packageIds, additionalParams = {}) {
        const context = {
            barcode_view: true,
            avoid_putaway_rules: true,
        };
        if (!this.groups.group_tracking_lot) {
            return this.notification(_t("To use packages, enable 'Packages' in the settings"), {
                type: "danger",
            });
        }
        if (!packageIds?.length) {
            // Nothing to do in this case
            return;
        }
        await this.save();
        const result = await this.orm.call("stock.package", "action_put_in_pack", [packageIds], {
            package_id: additionalParams.default_package_id,
            package_type_id: additionalParams.default_package_type_id,
            package_name: additionalParams.default_name,
            context,
        });
        if (typeof result === "object" && result.type) {
            this.trigger("process-action", result);
        } else {
            this.trigger("refresh");
        }
    }

    async unpack(linesToUnpack) {
        for (const line of linesToUnpack) {
            if (line.outermost_result_package_id) {
                await this.updateLine(line, { outermost_result_package_id: false });
            } else {
                await this.updateLine(line, { result_package_id: false });
            }
        }
        await this.save();
        this.trigger("update");
    }

    async _returnProducts() {
        const action = await this.orm.call(
            this.resModel,
            "action_create_return_picking",
            [[this.resId]],
            { context: this._getReturnContext() }
        );
        return this.action.doAction(action, { stackPosition: "replaceCurrentAction" });
    }

    _getReturnContext() {
        const returnContext = {};
        if (this.barcodeReturnReason) {
            returnContext.return_reason_id = this.barcodeReturnReason;
            this.barcodeReturnReason = undefined;
        }

        return returnContext;
    }

    async _scrap() {
        if (!this.canScrap) {
            const message = _t("You can't register scrap at this state of the operation");
            return this.notification(message, { type: "warning" });
        }
        await this.newScrapProduct();
    }

    /**
     * Set the pickings's responsible to the active user.
     */
    async _setUser() {
        if (this.record.id && this.record.user_id != user.userId) {
            this.record.user_id = user.userId;
            await this.orm.write(this.resModel, [this.record.id], { user_id: user.userId });
        }
    }

    _setLocationFromBarcode(result, location) {
        if (this.record.picking_type_code === "outgoing") {
            result.location = location;
        } else if (this.record.picking_type_code === "incoming") {
            result.destLocation = location;
        } else if (this.previousScannedLines.length || this.previousScannedLinesByPackage.length) {
            if (
                this.config.restrict_scan_source_location &&
                this.config.restrict_scan_dest_location === "no" &&
                this.barcodeInfo.class != "scan_dest"
            ) {
                result.location = location;
            } else {
                result.destLocation = location;
            }
        } else if (["scan_product_or_dest", "scan_dest"].includes(this.barcodeInfo.class)) {
            result.destLocation = location;
        } else {
            result.location = location;
        }
        return result;
    }

    _sortingMethod(l1, l2) {
        const l1IsCompleted = this._lineIsComplete(l1);
        const l2IsCompleted = this._lineIsComplete(l2);
        // Complete lines always on the bottom.
        if (!l1IsCompleted && l2IsCompleted) {
            return -1;
        } else if (l1IsCompleted && !l2IsCompleted) {
            return 1;
        }
        return super._sortingMethod(...arguments);
    }

    _updateLineQty(line, args) {
        if (args.qty_done) {
            if (line.product_id.tracking === "serial") {
                const nextQty = line.qty_done + args.qty_done;
                if (nextQty > 1 && (this.record.use_create_lots || this.record.use_existing_lots)) {
                    return; // Can't have more than 1 qty by serial number.
                }
            }
            line.qty_done += args.qty_done;
            this._setUser();
        }
    }

    _updateLotName(line, lotName) {
        line.lot_id = false;
        line.lot_name = lotName;
    }

    _canOverrideTrackingNumber(line, newLotName) {
        return (
            super._canOverrideTrackingNumber(...arguments) ||
            (this.location.id === line.location_id.id &&
                !line.package_id &&
                !line.owner_id &&
                this.getQtyDone(line) === 0)
        );
    }

    async _processGs1Data(data) {
        const result = await super._processGs1Data(...arguments);
        const { rule } = data;
        if (
            result.location &&
            (rule.type === "location_dest" || this.barcodeInfo.class === "scan_product_or_dest")
        ) {
            result.destLocation = result.location;
            result.location = undefined;
        }
        return result;
    }

    _getCompanyId() {
        return this.record.company_id;
    }

    mustTryPackUnscannedLine() {
        return !this.selectedLine || !this.selectedLine.qty_done;
    }
}
