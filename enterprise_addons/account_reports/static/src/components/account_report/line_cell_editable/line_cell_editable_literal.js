import { localization } from "@web/core/l10n/localization";

import { useHotkey } from "@web/core/hotkeys/hotkey_hook";
import { formatFloat } from "@web/core/utils/numbers";
import { parseFloat } from "@web/views/fields/parsers";

import { Component, signal, t, useProps } from "@odoo/owl";


export class AccountReportLineCellEditableLiteral extends Component {
    static template = "account_reports.AccountReportLineCellEditableLiteral";
    props = useProps({
        onChange: t.function(),
        cell: t.object(),
        audit: t.function(),
    });

    input = signal.ref();
    editPopupData = this.parseEditPopupData();

    isFocused = signal(false);

    inputRef = signal.ref();

    setup() {
        useHotkey(
            "Enter",
            ev => { ev.target.blur(); },
            { bypassEditableProtection: true },
        );
    }

    parseEditPopupData() {
        try {
            return JSON.parse(this.props.cell.edit_popup_data() || "{}");
        } catch {
            return {};
        }
    }

    get isLocaleFormatType() {
        return ["float", "integer", "monetary", "percentage"].includes(this.props.cell.figure_type());
    }

    get editableNumericValue() {
        const no_format = this.props.cell.no_format?.();
        if (no_format == null || no_format === "") {
            return no_format;
        }

        const numericValue = Number(no_format);
        if (Number.isNaN(numericValue)) {
            return no_format;
        }

        return formatFloat(numericValue, {
            digits: [0, this.editPopupData.rounding || 2],
            thousandsSep: "",
            grouping: [],
            trailingZeros: false,
        });
    }

    get editableValue() {
        const value = this.isLocaleFormatType
            ? this.editableNumericValue
            : this.props.cell.no_format();

        return value == null ? "" : String(value);
    }

    onClickEdit() {
        this.inputRef().focus();
    }

    async onChange() {
        let editValue = this.inputRef().value;

        if (this.isLocaleFormatType) {
            const otherDecimalSeparator = localization.decimalPoint === "." ? "," : ".";
            const localeThousandsSeparator = localization.thousandsSep || "";

            if (
                this.inputRef().value.split(localization.decimalPoint || ".").length >= 3 ||
                (this.inputRef().value.includes(otherDecimalSeparator) &&
                    otherDecimalSeparator !== localeThousandsSeparator)
            ) {
                editValue = this.inputRef().value;
            } else {
                try {
                    editValue = parseFloat(this.inputRef().value).toString();
                } catch {
                    editValue = this.inputRef().value;
                }
            }
        }

        await this.props.onChange(editValue);
        this.isFocused.set(false);
    }

    onFocus() {
        this.isFocused.set(true);
        this.inputRef().value = this.editableValue;
        this.inputRef().select();
    }

    onBlur() {
        if (this.editableValue === this.inputRef().value) {
            this.isFocused.set(false);
        }
    }

    onMouseDown(ev) {
        /**
         * This function has for purpose to prevent the input focus via the click without
         * blocking the click when the element is focus.
         */
        if (!this.isFocused()) ev.preventDefault();
    }

    audit() {
        if (this.isFocused()) return;
        this.props.audit();
    }

    get inputValue() {
        return this.isFocused() ? this.editableValue : this.props.cell.name();
    }
}
