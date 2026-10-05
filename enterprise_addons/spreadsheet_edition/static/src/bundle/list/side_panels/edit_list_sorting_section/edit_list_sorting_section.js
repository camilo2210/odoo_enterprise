import { Component, signal, t, useProps } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { CheckBox } from "@web/core/checkbox/checkbox";
import { localeCompare } from "@web/core/l10n/utils";
import { components, helpers, hooks } from "@odoo/o-spreadsheet";
import { _t } from "@web/core/l10n/translation";

const { AddDimensionButton, Section, Select } = components;
const { hasInteractiveElementInEventTree, getBoundingRectWithMargins } = helpers;

export class EditListSortingSection extends Component {
    static template = "spreadsheet_edition.EditListSortingSection";
    static components = { Dialog, CheckBox, AddDimensionButton, Section, Select };

    props = useProps({
        onUpdateSorting: t.function(),
        orderBy: t.array(),
        fields: t.object(),
        resModel: t.string(),
    });

    mainRef = signal.ref();
    dnd = hooks.useDragAndDropListItems();

    updateSorting(orderBy) {
        this.props.onUpdateSorting(orderBy);
    }

    isFieldAllowed(field) {
        return field.sortable && !this.props.orderBy.map((el) => el.name).includes(field.name);
    }

    getAllowedFields() {
        return Object.values(this.props.fields)
            .filter((field) => this.isFieldAllowed(field))
            .sort((a, b) => localeCompare(a.string, b.string));
    }

    onAddSortingRule(fieldName) {
        const orderByArray = [...this.props.orderBy, { name: fieldName, asc: true }];
        this.updateSorting(orderByArray);
    }

    onDeleteSortingRule(ruleIndex) {
        const orderByArray = [...this.props.orderBy];
        orderByArray.splice(ruleIndex, 1);
        this.updateSorting(orderByArray);
    }

    toggleAscending(ruleIndex) {
        const orderByArray = [...this.props.orderBy];
        orderByArray[ruleIndex] = {
            ...orderByArray[ruleIndex],
            asc: !orderByArray[ruleIndex].asc,
        };
        this.updateSorting(orderByArray);
    }

    getSortingRuleElementsRects() {
        return Array.from(this.mainRef().children).map((el) => getBoundingRectWithMargins(el));
    }

    startDragAndDrop(rule, event) {
        if (event.button !== 0 || hasInteractiveElementInEventTree(event)) {
            return;
        }
        const rects = this.getSortingRuleElementsRects();
        const items = this.props.orderBy.map((r, index) => ({
            id: r.name,
            size: rects[index].height,
            position: rects[index].y,
        }));
        this.dnd.start("vertical", {
            draggedItemId: rule.name,
            initialMousePosition: event.clientY,
            items,
            scrollableContainerEl: this.mainRef().closest(".o-sidePanelBody") || this.mainRef(),
            onDragEnd: (ruleName, finalIndex) => {
                const orderByArray = [...this.props.orderBy];
                const originalIndex = orderByArray.findIndex((r) => r.name === ruleName);
                if (originalIndex === finalIndex) {
                    return;
                }
                const [movedRule] = orderByArray.splice(originalIndex, 1);
                orderByArray.splice(finalIndex, 0, movedRule);
                this.updateSorting(orderByArray);
            },
        });
    }

    get sortingOptions() {
        return [
            { value: "true", label: _t("Ascending") },
            { value: "false", label: _t("Descending") },
        ];
    }
}
