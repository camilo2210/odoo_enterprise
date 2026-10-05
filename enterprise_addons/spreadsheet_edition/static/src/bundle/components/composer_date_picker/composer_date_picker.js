import { components, stores, helpers } from "@odoo/o-spreadsheet";
import { patch } from "@web/core/utils/patch";
import { DateTimePickerPopover } from "@web/core/datetime/datetime_picker_popover";
import { usePopover } from "@web/core/popover/popover_hook";
import { Component, useProps, t, useEffect } from "@odoo/owl";
import { dateTimePickerProps } from "@web/core/datetime/datetime_picker";

const { Composer } = components;
const { CellComposerStore } = stores;
const { DateTime } = luxon;
const { numberToJsDate, parseFormat, isFormula } = helpers;

patch(CellComposerStore.prototype, {
    get isDateCell() {
        return this.cellFormat ? isDateFormat(this.cellFormat) : false;
    },
    get cellFormat() {
        return this.getters.getEvaluatedCell(this.currentEditedCell).format;
    },
    get rawCellValue() {
        return this.getters.getEvaluatedCell(this.currentEditedCell).value;
    },
});

Composer.components = { ...Composer.components };
patch(Composer.prototype, {
    setup() {
        super.setup();
        this.popover = usePopover(ComposerDatePickerPopover, { position: "bottom-start" });
        useEffect(() => {
            if (this.shouldDisplayDatePicker() && !this.popover.isOpen) {
                this.openDatePicker();
            } else if (!this.shouldDisplayDatePicker() && this.popover.isOpen) {
                this.popover.close();
            }
        });
    },
    selectDate(date) {
        this.props.composerStore.setCurrentContent(`${date.month}/${date.day}/${date.year}`);
        this.props.composerStore.stopEdition();
    },
    shouldDisplayDatePicker() {
        return (
            this.props.focus !== "inactive" &&
            this.props.composerStore.isDateCell &&
            !isFormula(this.props.composerStore.currentContent) &&
            !this.props.composerStore.autoCompleteProposals?.length
        );
    },
    openDatePicker() {
        const dateValue = cellValueToDateTime(this.props.composerStore.rawCellValue);
        this.popover.open(this.composerRef(), {
            pickerProps: {
                onSelect: async (value) => {
                    this.selectDate(value);
                    this.popover.close();
                },
                type: "date",
                value: dateValue,
            },
        });
    },
});

export class ComposerDatePickerPopover extends Component {
    // Inline copy of DateTimePickerPopover's props schema (no exported const upstream)
    props = useProps({
        close: t.function(),
        pickerProps: t.object(dateTimePickerProps),
    });
    static components = { DateTimePickerPopover };
    static template = "spreadsheet_edition.ComposerDatePickerPopover";
}

function cellValueToDateTime(cellValue) {
    if (typeof cellValue !== "number") {
        return undefined;
    }
    const jsDate = numberToJsDate(cellValue).jsDate;
    return DateTime.fromJSDate(jsDate);
}

function isDateFormat(format) {
    const internalFormat = parseFormat(format)?.positive;
    return internalFormat?.type !== "date"
        ? false
        : internalFormat.tokens.some(
              (token) => token.type === "DATE_PART" && token.value.match(/[dmy]/)
          );
}
