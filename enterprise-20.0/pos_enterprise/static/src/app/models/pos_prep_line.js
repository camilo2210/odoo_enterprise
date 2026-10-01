import { registry } from "@web/core/registry";
import { Base } from "@point_of_sale/app/models/related_models";
import { computeDurationSinceDate, roundQuantity } from "@pos_enterprise/app/utils/utils";

const { DateTime } = luxon;

export class PosPrepLine extends Base {
    static pythonModel = "pos.prep.line";

    setup(vals) {
        super.setup(vals);
        this.timeToShow = 0;

        // Only lines with a stage are "active" preparation lines (combo parents are excluded)
        if (!this.stage_id) {
            return;
        }
        const orderPresetTime = this.prep_order_id.pos_order_id.preset_time;
        if (orderPresetTime) {
            const preset = this.prep_order_id.pos_order_id.preset_id;
            if (preset && preset.nextSlot?.datetime.ts < orderPresetTime.ts) {
                this.timeToShow =
                    orderPresetTime.minus({ minutes: preset.interval_time }) - DateTime.now();
                setTimeout(() => {
                    this.timeToShow = 0;
                }, this.timeToShow);
            }
        }
    }

    get product() {
        return this.product_id;
    }

    get categories() {
        return this.product.pos_categ_ids;
    }

    get todoQuantity() {
        return roundQuantity(this.quantity - this.cancelled, this.models);
    }

    get roundedQuantity() {
        return roundQuantity(this.quantity, this.models);
    }

    get roundedCancelled() {
        return roundQuantity(this.cancelled, this.models);
    }

    get isCancelled() {
        return this.quantity - this.cancelled === 0;
    }

    computeDuration() {
        return computeDurationSinceDate(this.last_stage_change);
    }

    isStageDone(todo = false) {
        return this.stage_id.id === this.raw.last_stage_id && this.todo === todo;
    }
}

registry.category("pos_available_models").add(PosPrepLine.pythonModel, PosPrepLine);
