import { Component, onWillStart, proxy, signal, useProps } from "@odoo/owl";
import { AutoComplete } from "@web/core/autocomplete/autocomplete";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { BadgeTag } from "@web/core/tags_list/badge_tag";
import { standardFieldProps } from "@web/views/fields/standard_field_props";


export class UserGroupbyWidget extends Component {
    static template="account_reports.UserGroupbyWidget";
    static components = {
        AutoComplete,
        BadgeTag,
    };
    props = useProps(standardFieldProps);

    elRef = signal.ref();

    state = proxy({ cursorIndex: this.groupbyList.length });
    
    fieldService = useService("field");

    setup() {
        super.setup();
        onWillStart(async () => {
            const move_line_fields = await this.fieldService.loadFields('account.move.line');
            this.fields = Object.fromEntries(
                Object.entries(move_line_fields).filter(([_fieldName, fieldData]) => fieldData.groupable)
            );
        });
    }

    get groupbyList() {
        const groupbyStr = this.props.record.data[this.props.name].trim();
        if (groupbyStr) {
            return groupbyStr.split(',').map(expr => expr.trim());
        }
        return [];
    }

    get tags() {
        return this.groupbyList.map((groupby, index) => {
            const isField = groupby in this.fields;
            return {
                text: isField? this.fields[groupby].string: groupby,
                onDelete: () => this.removeGroupby(index),
                colorIndex: isField? 4: 0,
            }
        });
    }

    get sources() {
        return [{ options: this.getOptions.bind(this) }];
    }

    /**
     * Index of the cursor, if the focus is on an input element.
     */
    get focusedInputIndex() {
        const inputElArray = [...this.elRef().querySelectorAll(".o_account_reports_groupby_input")];
        return inputElArray.indexOf(this.focusedEl);
    }

    /**
     * If the focus is on a groupby, index of that groupby.
     */
    get focusedGroupbyIndex() {
        const badgeElArray = [...this.elRef().querySelectorAll(".o_account_reports_groupby")];
        return badgeElArray.indexOf(this.focusedEl);
    }

    async getOptions(request) {
        const options = [];

        const value = request.trim().toLowerCase();
        for (const [field_name, fieldData] of Object.entries(this.fields)) {
            if (
                !this.groupbyList.includes(field_name)
                && (field_name.includes(value) || fieldData.string.toLowerCase().includes(value))
            ) {
                options.push({
                    label: fieldData.string,
                    onSelect: () => this.addGroupby(field_name),
                })
            }
        }

        return options;
    }

    // -----------------------------------------------------------------------------
    // EDIT & NAVIGATION
    // -----------------------------------------------------------------------------

    updateGroupbyList(newList) {
        this.props.record.update({
            [this.props.name]: newList.join(','),
        });
    }

    /**
     * No need to provide the index of the groupby to add, as it is where the cursor is.
     */
    addGroupby(groupby) {
        const newGroupbyList = this.groupbyList;
        if (this.focusedInputIndex == -1) {
            return;
        }

        newGroupbyList.splice(this.focusedInputIndex, 0, groupby);
        this.updateGroupbyList(newGroupbyList);
    }

    removeGroupby(index) {
        const newGroupbyList = this.groupbyList;

        newGroupbyList.splice(index, 1);
        this.updateGroupbyList(newGroupbyList);
    }

    /**
     * Necessary because if focusing the input, we don't want to focus the div but the input element.
     */
    focusEl(el) {
        if (el.classList.contains("o_account_reports_groupby_input")) {
            el.querySelector("input").focus();
        } else {
            el.focus();
        }
        this.focusedEl = el;
    }

    moveFocusLeft() {
        const prevSibling = this.focusedEl.previousElementSibling;
        if (prevSibling) {
            this.focusEl(prevSibling);
        }
    }

    moveFocusRight() {
        const nextSibling = this.focusedEl.nextElementSibling;
        if (nextSibling) {
            this.focusEl(nextSibling);
        }
    }

    // -----------------------------------------------------------------------------
    // EVENTS
    // -----------------------------------------------------------------------------

    /**
     * To keep track of which subelement is focused (an input or a groupby)
     */
    onFocusin(event) {
        for (const el of this.elRef().children) {
            if (el.contains(event.target)) {
                this.focusedEl = el;
                return;
            }
        }
    }

    /**
     * Set navigation events, the deletion of a groupby with "Backspace"
     * and the creation of a groupby with "Enter".
     */
    onKeydown(event) {
        if (this.focusedEl.classList.contains("o_account_reports_groupby_input")) {  // events if we are focusing an input
            const inputEl = this.focusedEl.querySelector("input");
            if (!inputEl.value) {
                if (event.key === 'Backspace' && this.focusedInputIndex > 0) {
                    this.removeGroupby(this.focusedInputIndex - 1);
                } else if (event.key === 'ArrowLeft') {
                    this.moveFocusLeft();
                } else if (event.key === 'ArrowRight') {
                    this.moveFocusRight();
                }
            } else if (event.key === 'Enter') {
                this.addGroupby(inputEl.value.trim());
                inputEl.value = "";
                inputEl.style.width = 0;
            }
        } else {
            if (event.key === 'Backspace') {
                this.removeGroupby(this.focusedGroupbyIndex);
            } else if (event.key === 'ArrowLeft') {
                this.moveFocusLeft();
            } else if (event.key === 'ArrowRight') {
                this.moveFocusRight();
            }
        }
    }

    /**
     * To get a dynamic input element size.
     */
    onInput() {
        const inputEl = this.focusedEl.querySelector("input");
        inputEl.style.width = inputEl.value.length + 'ch';
    }

}

export const userGroupbyWidget = {
    component: UserGroupbyWidget,
    supportedTypes: ["char"],
}

registry.category("fields").add("user_groupby_widget", userGroupbyWidget);
