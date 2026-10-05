import { Component, signal, t, useProps } from "@odoo/owl";
import { components, helpers, hooks, CompiledFormula } from "@odoo/o-spreadsheet";

const { TextInput, StandaloneComposer } = components;
const {
    collapseHierarchicalDisplayName,
    hasInteractiveElementInEventTree,
    getBoundingRectWithMargins,
    unquote,
    getCanonicalSymbolName,
} = helpers;

const LIST_TOKEN_COLOR = "#F28C28";

export class ListDimensions extends Component {
    static template = "spreadsheet_edition.ListDimensions";
    static components = { TextInput, StandaloneComposer };

    props = useProps({
        dimensions: t.array(),
        onRemoved: t.function(),
        onNameUpdated: t.function(),
        onFormulaUpdate: t.function(),
        updateOrder: t.function(),
        toggleVisibility: t.function(),
    });

    dimensionsContainerRef = signal.ref();
    dnd = hooks.useDragAndDropListItems();

    updateName(dimension, name) {
        this.props.onNameUpdated(dimension, name === "" || name.startsWith("=") ? undefined : name);
    }

    getDimensionCollapsedName(dimensionName) {
        return collapseHierarchicalDisplayName(dimensionName);
    }

    getDimensionElementsRects() {
        return Array.from(this.dimensionsContainerRef().children).map((el) =>
            getBoundingRectWithMargins(el)
        );
    }

    startDragAndDrop(dimension, event) {
        if (event.button !== 0 || hasInteractiveElementInEventTree(event)) {
            return;
        }
        const rects = this.getDimensionElementsRects();
        const items = this.props.dimensions.map((dim, index) => ({
            id: dim.name,
            size: rects[index].height,
            position: rects[index].y,
        }));
        this.dnd.start("vertical", {
            draggedItemId: dimension.name,
            initialMousePosition: event.clientY,
            items,
            scrollableContainerEl:
                this.dimensionsContainerRef().closest(".o-sidePanelBody") ||
                this.dimensionsContainerRef(),
            onDragEnd: (dimensionName, finalIndex) => {
                const dimensions = this.props.dimensions.map((dim) => dim.name);
                const originalIndex = dimensions.findIndex((name) => name === dimensionName);
                if (originalIndex === finalIndex) {
                    return;
                }
                dimensions.splice(originalIndex, 1);
                dimensions.splice(finalIndex, 0, dimensionName);
                this.props.updateOrder(dimensions);
            },
        });
    }

    isCalculatedColumnInvalid(dimension) {
        return CompiledFormula.IsBadExpression(dimension.computedBy?.formula ?? "");
    }

    getColoredSymbolToken(token) {
        if (token.type !== "SYMBOL") {
            return undefined;
        }
        const tokenValue = unquote(token.value, "'");
        if (this.props.dimensions.some((col) => col.name === tokenValue)) {
            return LIST_TOKEN_COLOR;
        }
        return undefined;
    }

    getCalculatedColumnAutoComplete(forColumn) {
        const dimensions = this.props.dimensions;
        const columnProposals = dimensions
            .filter((m) => m.name !== forColumn.name)
            .map((column) => {
                const text = getCanonicalSymbolName(column.name);
                return {
                    text: text,
                    description: column.string,
                    htmlContent: [{ value: column.name, color: LIST_TOKEN_COLOR }],
                    fuzzySearchKey: column.string + text,
                };
            });
        return {
            sequence: 0,
            autoSelectFirstProposal: true,
            getProposals(tokenAtCursor) {
                return columnProposals;
            },
            selectProposal(tokenAtCursor, proposal) {
                let start = tokenAtCursor.end;
                if (tokenAtCursor.type === "SYMBOL") {
                    start = tokenAtCursor.start;
                }
                const end = tokenAtCursor.end;
                this.composer.changeComposerCursorSelection(start, end);
                this.composer.replaceComposerCursorSelection(proposal.text);
            },
        };
    }
}
