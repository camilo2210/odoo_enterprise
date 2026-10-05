import { Component, computed, signal, t, useProps } from "@odoo/owl";
import { SelectMenu } from "@web/core/select_menu/select_menu";

export class AccountReportLineCellEditableSelection extends Component {
    static template = "account_reports.AccountReportLineCellEditableSelection";
    static components = { SelectMenu };
    props = useProps({
        onChange: t.function(),
        cell: t.object(),
        audit: t.function(),
    });

    selectionRef = signal.ref();
    selectionChoices = computed(() => this.parseSelectionOptions());
    isFocused = signal(false);

    parseSelectionOptions() {
        try {
            const editPopupData = JSON.parse(this.props.cell.edit_popup_data() ?? "{}");
            if (!editPopupData.selection_options) {
                return [];
            }
            const choices = [];
            for (const [value, label] of Object.entries(editPopupData.selection_options)) {
                choices.push({ value, label });
            }
            return choices;
        } catch {
            return [];
        }
    }

    getSelectedChoiceLabel(value) {
        return this.selectionChoices().find((choice) => choice.value === value)?.label;
    }

    onClickSelection() {
        const el = this.selectionRef().querySelector(".o_select_menu_toggler, input");
        if (el) {
            this.isFocused.set(true);
            // Focus and click both are needed since focus helps user to type in options in input, and click shows dropdown
            el.focus();
            el.click();
        }
    }

    onSelectOpened() {
        this.isFocused.set(true);
    }

    onSelectClosed() {
        this.isFocused.set(false);
    }

    async onSelectChoice(choice) {
        await this.props.onChange(this.getSelectedChoiceLabel(choice));
        this.isFocused.set(false);
    }

    get selectionValue() {
        return (
            this.selectionChoices().find((option) => option.label === this.props.cell.name?.())?.value ||
            ""
        );
    }
}
