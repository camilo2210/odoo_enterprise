import { _t } from "@web/core/l10n/translation";
import { localization } from "@web/core/l10n/localization";
import { escapeRegExp } from "@web/core/utils/strings";
import { useAutofocus, useService } from "@web/core/utils/hooks";
import { formatFloat, formatPercentage } from "@web/views/fields/formatters";
import { Component, useProps, proxy, signal, t } from "@odoo/owl";

export class HelpdeskTeamTarget extends Component {
    static template = "helpdesk.HelpdeskTeamTarget";
    props = useProps({
        showDemo: t.boolean().optional(false),
        demoClass: t.string().optional(""),
        update: t.function(),
        percentage: t.boolean().optional(false),
        rating: t.boolean().optional(false),
        value: t.number(),
        hotkey: t.string().optional(),
    });

    inputRef = signal.ref();

    setup() {
        useAutofocus({ ref: this.inputRef, selectAll: true });
        this.notification = useService("notification");
        this.state = proxy({
            isFocused: false,
            value: this.props.value,
        });
    }

    get valueString() {
        return this.props.rating
            ? `${this.state.value} / 5`
            : !this.props.percentage
            ? this.state.value
            : formatPercentage(this.state.value / 100);
    }

    get helpdeskTeamTargetTitle() {
        if (this.props.showDemo) {
            return _t("Average rating daily target");
        } else if (this.props.rating) {
            return _t("Click to Set Your Daily Rating Target");
        } else {
            return _t("Click to set");
        }
    }

    /**
     * @private
     */
    _toggleFocus() {
        this.state.isFocused = !this.state.isFocused;
    }

    /**
     * Handle the keydown event on the value input
     *
     * @private
     * @param {KeyboardEvent} ev
     */
    _onInputKeydown(ev) {
        if (ev.key === "Enter") {
            this.inputRef()?.blur();
        }
    }

    /**
     * @private
     */
    async _onValueChange() {
        let inputValue = this.inputRef().value;
        // a number can have the thousand separator multiple times. ex: 1,000,000.00
        inputValue = inputValue.replaceAll(
            new RegExp(escapeRegExp(localization.thousandsSep || ""), "g") || ",",
            ""
        );
        const targetValue = this.props.rating ? parseFloat(inputValue) : parseInt(inputValue);
        if (Number.isNaN(targetValue)) {
            this.notification.add(_t("Please enter a number."), { type: "danger" });
            return;
        }
        if (targetValue <= 0) {
            this.notification.add(_t("Please enter a positive value."), { type: "danger" });
            return;
        }
        if (this.props.percentage && targetValue > 100) {
            this.notification.add(_t("Please enter a percentage below 100."), { type: "danger" });
            return;
        } else if (this.props.rating && targetValue > 5) {
            this.notification.add(_t("Please enter a value less than or equal to 5."), {
                type: "danger",
            });
            return;
        }
        this.state.value = formatFloat(targetValue, { digits: [1, 0] });
        await this.props.update(targetValue);
    }
}
