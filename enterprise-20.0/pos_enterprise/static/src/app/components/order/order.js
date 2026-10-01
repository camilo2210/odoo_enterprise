import { Component, computed, onWillUnmount, proxy, useProps, signal, t } from "@odoo/owl";
import { usePrepDisplay } from "@pos_enterprise/app/services/preparation_display_service";
import { Orderline } from "@pos_enterprise/app/components/orderline/orderline";
import { computeFontColor, useDelayedValueChange } from "@pos_enterprise/app/utils/utils";
import { BadgeTag } from "@web/core/tags_list/badge_tag";
import { logPosMessage } from "@point_of_sale/app/utils/pretty_console_log";
import { PosPrepOrder } from "@pos_enterprise/app/models/pos_preparation_order";
import { PosPrepStage } from "@pos_enterprise/app/models/pos_preparation_stage";
import { PosPrepLine } from "@pos_enterprise/app/models/pos_prep_line";
import { _t } from "@web/core/l10n/translation";
const { DateTime } = luxon;

export class Order extends Component {
    static components = { Orderline, BadgeTag };
    static template = "pos_enterprise.Order";
    props = useProps({
        order: t.object({
            prepOrder: t.instanceOf(PosPrepOrder),
            stage: t.instanceOf(PosPrepStage),
            prepLines: t.array(t.instanceOf(PosPrepLine)),
        }),
    });

    orderlinesContainerRef = signal.ref();

    // Drives the card animation while the order is moving to another stage.
    isStageChanging = computed(() =>
        this.prepDisplay.stageChangedOrderIds?.includes(this.order?.id)
    );

    setup() {
        this.prepDisplay = usePrepDisplay();
        this.state = proxy({
            duration: 0,
        });
        this.actionInProgress = false;
        this._updateDuration();
        this.interval = setInterval(() => {
            if (this.order && this.order.pos_order_id) {
                this._updateDuration();
            } else {
                clearInterval(this.interval);
            }
        }, 1000);
        onWillUnmount(() => {
            clearInterval(this.interval);
        });

        this.internalNoteState = useDelayedValueChange(() => this.order.pos_order_id.internal_note);
    }

    _updateDuration() {
        this.state.duration = this._computeDuration();
    }
    get order() {
        return this.props.order.prepOrder;
    }
    get presetTime() {
        return this.order.pos_order_id.formatDateOrTime("preset_time", "time");
    }

    get presetDate() {
        const preset_time = this.order.pos_order_id.preset_time;
        if (!preset_time) {
            return "";
        }
        const today = DateTime.now();

        if (preset_time.hasSame(today, "day")) {
            return _t("Today");
        }
        if (preset_time.hasSame(today.plus({ days: 1 }), "day")) {
            return _t("Tomorrow");
        }
        return this.order.pos_order_id.formatDateOrTime("preset_time", "date");
    }

    get fontColor() {
        return computeFontColor(this.props.order.stage.color);
    }

    getChildPreparationLineStates(orderline_id) {
        return this.props.order.prepLines.filter(
            (pl) => pl.combo_parent_id?.id === orderline_id.id
        );
    }

    get orderlines() {
        const orderlines = [];
        for (const line of this.props.order.prepLines) {
            if (orderlines.includes(line)) {
                continue;
            }
            const parent_preparation_line = line.combo_parent_id;
            if (parent_preparation_line) {
                const children = this.getChildPreparationLineStates(parent_preparation_line);
                const allChildrenAreFalse = children.every((child) => child.todo === false);
                parent_preparation_line.todo = !allChildrenAreFalse;
                orderlines.push(parent_preparation_line, ...children);
            } else {
                if (orderlines.includes(line)) {
                    continue;
                }
                orderlines.push(line);
            }
        }
        return orderlines;
    }

    _computeDuration() {
        const timeDiff = this._getOrderDuration();
        if (timeDiff > this.props.order.stage.alert_timer) {
            this.isAlert = true;
        } else {
            this.isAlert = false;
        }

        return timeDiff;
    }

    changeOrderlineStatus(prepLine) {
        const lastStage = prepLine.raw.last_stage_id;
        if (this.props.order.stage.id === lastStage) {
            return;
        }
        const newState = !prepLine.todo;
        prepLine.todo = newState;
        if (prepLine.combo_line_ids.length > 0) {
            this.getChildPreparationLineStates(prepLine).forEach((state_line) => {
                state_line.todo = newState;
            });
        }

        if (this.props.order.prepLines.some((pl) => pl.todo)) {
            this.prepDisplay.syncStateStatus(this.props.order.prepLines);
        } else {
            this.prepDisplay.changeStateStageAnimation(
                this.props.order,
                this.props.order.prepLines
            );
        }
    }

    get order_name() {
        return (
            this.order.pos_order_id.floating_order_name || this.order.pos_order_id.tracking_number
        );
    }
    _getOrderDuration() {
        return Math.max(...this.props.order.prepLines.map((pl) => pl.computeDuration()));
    }

    async doneOrder() {
        this.prepDisplay.doneOrders(this.props.order.prepLines);
    }

    get cardColor() {
        return "o_pdis_card_color_0";
    }

    async clickOrder() {
        if (this.actionInProgress) {
            return;
        }
        try {
            this.actionInProgress = true;
            if (this.props.order.prepLines.every((pl) => pl.stage_id.id === pl.raw.last_stage_id)) {
                return;
            } else {
                const strickedLine = this.props.order.prepLines.filter((l) => !l.todo);

                await this.prepDisplay.changeStateStageAnimation(
                    this.props.order,
                    strickedLine.length ? strickedLine : this.props.order.prepLines
                );
            }
        } catch (error) {
            logPosMessage("Order", "clickOrder", "Error clicking order", false, [error]);
        } finally {
            this.actionInProgress = false;
        }
    }
    get pdisNotes() {
        return JSON.parse(this.order.pos_order_id.internal_note || null);
    }
}
