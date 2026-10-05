import { isHtmlContentSupported } from "@html_editor/core/selection_plugin";
import { DynamicFieldPlugin } from "@html_editor/backend/dynamic_field/dynamic_field_plugin";
import { ColorUIPlugin as _ColorUIPlugin } from "@html_editor/main/font/color_ui_plugin";
import { closestElement, traverseNode } from "@html_editor/utils/dom_traversal";
import { nodeSize } from "@html_editor/utils/position";
import { withSequence } from "@html_editor/utils/resource";
import { sortBy } from "@web/core/utils/arrays";
import { _t } from "@web/core/l10n/translation";

import { QWebPlugin } from "@html_editor/others/qweb_plugin";
import { MAIN_PLUGINS } from "@html_editor/plugin_sets";
import { QWebTablePlugin } from "./qweb_table_plugin";
import { getDeepestPosition } from "@html_editor/utils/dom_info";

function* iterChain(...iterables) {
    for (const it of iterables) {
        yield* it;
    }
}

function getQwebVariables(element, isInHeaderFooter) {
    if (!element) {
        return {};
    }

    const nodeOeContext = element.closest("[oe-context]");
    const qwebVariables = nodeOeContext && JSON.parse(nodeOeContext.getAttribute("oe-context"));
    if (isInHeaderFooter) {
        const companyVars = Object.entries(qwebVariables).filter(
            ([k, v]) => v.model === "res.company"
        );
        return Object.fromEntries(companyVars);
    } else {
        return qwebVariables || {};
    }
}

export class ReportEditorPlugin extends DynamicFieldPlugin {
    static id = "report_editor_main";
    static dependencies = [
        ...DynamicFieldPlugin.dependencies,
        "hint",
        "domObserver",
        "domReferenceMap",
    ];

    resources = {
        ...this.resources,
        is_node_splittable_predicates: (node) => {
            if (node.nodeType === Node.ELEMENT_NODE && node.matches(".page, .header, .footer")) {
                return false;
            }
        },
        user_commands: [
            {
                ...this.resources.user_commands[0],
                isAvailable: (selection) => this.isInsertAvailable(selection),
            },
            this.resources.user_commands[1],
            {
                id: "insertDynamicTable",
                title: _t("Dynamic Table"),
                description: _t("Insert a table based on a relational field."),
                icon: "database",
                run: this.insertTable.bind(this),
                isAvailable: (selection) => this.isInsertAvailable(selection),
            },
        ],
        powerbox_items: [
            ...this.resources.powerbox_items,
            withSequence(25, {
                categoryId: "dynamic_field_tools",
                commandId: "insertDynamicTable",
            }),
        ],
        on_editor_started_handlers: this.startHinting.bind(this),
        on_inserted_handlers: this.elementInsertedHandler.bind(this),
        on_dynamic_field_edit_applied_handlers: this.onFieldApply.bind(this),
        on_pending_mutations_staged_handlers: this.handleDomMutations.bind(this),
        normalize_processors: [
            this.resources.normalize_processors,
            this.protectCrackParents.bind(this),
        ],
        can_contain_selection_placeholder_predicates:
            this.selection_placeholder_container_predicates.bind(this),
    };

    onSelectionChanged(selection) {
        super.onSelectionChanged(selection);
        if (selection.documentSelection && this.config.setEditingReport) {
            const closestViewId = closestElement(
                selection.documentSelection.anchorNode,
                "[ws-view-id]"
            );
            const closestCallViewId = closestElement(
                selection.documentSelection.anchorNode,
                "[ws-view-id][t-name]"
            );
            if (closestViewId && closestCallViewId) {
                const name =
                    closestViewId.getAttribute("t-name") ||
                    closestViewId.getAttribute("ws-view-name");
                const shared = name === closestCallViewId.getAttribute("t-name");
                this.config.setEditingReport(name, shared);
            } else {
                this.config.setEditingReport("", false);
            }
        }
    }

    protectCrackParents(root) {
        this.protectedCracksParents = this.getProtectedLayoutCracksParents();
        return root;
    }

    getProtectedLayoutCracksParents() {
        const parents = new Map();
        for (const el of this.editable.querySelectorAll(".header,.article,.footer")) {
            parents.set(el.parentElement, true);
        }
        return parents;
    }

    selection_placeholder_container_predicates(container) {
        if (this.protectedCracksParents.has(container)) {
            return false;
        }
        if (["header", "footer"].some((cls) => container.classList.contains(cls))) {
            return true;
        }
        if (container.classList.contains("article")) {
            const viewNode = container.closest("[ws-view-id]");
            const viewName =
                viewNode?.getAttribute("t-name") || viewNode?.getAttribute("ws-view-name");
            if (viewName && viewName.startsWith("web.")) {
                return false;
            }
        }
    }

    fieldTagName = "SPAN";
    fieldAttribute = "t-field";

    isInsertAvailable(selection) {
        if (!isHtmlContentSupported(selection)) {
            return;
        }

        const { anchorNode } = this.dependencies.selection.getEditableSelection();
        const target = anchorNode.nodeType === 1 ? anchorNode : anchorNode.parentElement;

        const isInHeaderFooter = closestElement(target, ".header,.footer");
        const qwebVariables = getQwebVariables(target, isInHeaderFooter);
        const qwebVar = this.getQwebVariable(target, qwebVariables, isInHeaderFooter);

        return !!qwebVar;
    }

    async insertTable() {
        const { anchorNode } = this.dependencies.selection.getEditableSelection();
        const target = anchorNode.nodeType === 1 ? anchorNode : anchorNode.parentElement;

        const resModel = this.getResModel(target);

        this.fieldPopover.open({
            target,
            props: {
                resModel,
                followRelation: false,
                disableLabel: true,
                filter: (fieldDef, path) => ["one2many", "many2many"].includes(fieldDef.type),
                close: () => this.fieldPopover.close(),
                validate: async ({ path, fieldInfo }) => {
                    const doc = this.document;
                    doc.defaultView.focus();

                    const selection = this.dependencies.selection.preserveSelection();
                    const table = this.document.createElement("table");
                    table.classList.add("table", "table-sm");

                    const tBody = table.createTBody();
                    const topRow = tBody.insertRow();
                    topRow.classList.add(
                        "border-bottom",
                        "border-top-0",
                        "border-start-0",
                        "border-end-0",
                        "border-2",
                        "border-dark",
                        "fw-bold"
                    );
                    const topTd = this.document.createElement("td");
                    topTd.appendChild(
                        this.document.createTextNode(fieldInfo.string || "Column name")
                    );
                    topRow.appendChild(topTd);

                    const tr = this.document.createElement("tr");
                    tr.setAttribute("t-foreach", this.getFieldPath(target, path));
                    tr.setAttribute("t-as", "x2many_record");

                    const isInHeaderFooter = closestElement(target, ".header,.footer");
                    const qwebVariables = getQwebVariables(target, isInHeaderFooter);
                    tr.setAttribute(
                        "oe-context",
                        JSON.stringify({
                            x2many_record: {
                                model: fieldInfo.relation,
                                in_foreach: true,
                                name: fieldInfo.relationName,
                            },
                            ...qwebVariables,
                        })
                    );
                    tBody.appendChild(tr);

                    await this.config.dynamicFieldPostprocess?.({
                        fieldInfo,
                        element: tr,
                    });

                    const td = this.document.createElement("td");
                    td.textContent = _t("Insert a field...");
                    tr.appendChild(td);

                    selection.restore();
                    this.dependencies.dom.insert(table);
                    this.editable.focus();
                    this.dependencies.selection.setSelection({
                        anchorNode: td,
                        focusOffset: nodeSize(td),
                    });
                    this.dependencies.history.commit();
                },
            },
        });
    }

    getResModel(element) {
        const isInHeaderFooter = closestElement(element, ".header,.footer");
        const qwebVariables = getQwebVariables(element, isInHeaderFooter);
        const qwebVar = this.getQwebVariable(element, qwebVariables, isInHeaderFooter);
        let resModel = qwebVariables[qwebVar]?.model;
        if (!resModel) {
            resModel = this.resModel;
        }
        return resModel;
    }

    followRelation({ fieldDef }) {
        if (["many2many", "one2many"].includes(fieldDef.type)) {
            return false;
        }
    }

    filter(fieldDef, path) {
        if (fieldDef.type === "properties") {
            return false;
        }
        if (["one2many", "many2many"].includes(fieldDef.type)) {
            return true;
        }
        return super.filter(fieldDef, path);
    }

    getFieldPath(element, fieldPath) {
        const resModel = this.getResModel(element);
        const isInHeaderFooter = closestElement(element, ".header,.footer");
        const qwebVariables = getQwebVariables(element, isInHeaderFooter);

        let qwebVar = this.getQwebVariable(element, qwebVariables, isInHeaderFooter);
        if (!qwebVar) {
            const sortedVariables = this.getSortedVariables(
                resModel,
                qwebVariables,
                isInHeaderFooter
            );
            qwebVar =
                sortedVariables.find((varName) => ["doc", "o"].includes(varName)) ||
                sortedVariables.find((varName) => qwebVariables[varName].model === resModel);
        }

        return `${qwebVar}.${fieldPath}`;
    }

    /**
     * @param {HTMLElement[]} insertedNodes
     */
    elementInsertedHandler(insertedNodes) {
        for (const node of insertedNodes) {
            if (
                node.tagName === "TABLE" &&
                node.classList.contains("o_table") &&
                closestElement(node, "[t-call='web.external_layout']")
            ) {
                node.removeAttribute("class");
                node.classList.add("table", "o_table", "table-borderless");
            }
        }
    }

    /**
     * @param {import("@html_editor/core/dom_observer_plugin").SerializedMutation[]} records
     */
    handleDomMutations(records) {
        const CUSTOM_BRANDING_ATTR = [
            "ws-view-id",
            "ws-view-name",
            "ws-call-key",
            "ws-call-group-key",
            "ws-real-children",
            "o-diff-key",
        ];

        for (const record of records) {
            if (record.isAutomatic) {
                continue;
            }
            if (record.type === "attributes") {
                if (record.attributeName === "contenteditable") {
                    continue;
                }
                if (record.attributeName.startsWith("data-oe-t")) {
                    continue;
                }
            }
            let target = this.dependencies.domReferenceMap.getNodeById(record.nodeId);
            if (record.type === "add") {
                if (target.nodeType === Node.ELEMENT_NODE) {
                    traverseNode(target, (node) => {
                        CUSTOM_BRANDING_ATTR.forEach((attr) => {
                            node.removeAttribute(attr);
                        });
                        node.classList.remove("o_dirty");
                    });
                }
            }
            if (record.type === "remove") {
                if (target.nodeType === Node.COMMENT_NODE) {
                    continue;
                }
            }

            if (!target.isConnected) {
                continue;
            }
            if (target.nodeType !== Node.ELEMENT_NODE) {
                target = target.parentElement;
            }
            if (!target) {
                continue;
            }

            target = target.closest(`[ws-view-id]`);
            if (!target) {
                continue;
            }
            target.classList.add("o_dirty");
        }
    }

    startHinting() {
        const doc = this.document;
        (doc.defaultView.frameElement || doc.defaultView).focus();
        for (const hintable of this.getHintables()) {
            // Force the selection to the hintable
            // Do it with the Selection API to make sure
            // the (visual) cursor is correctly set
            const r = doc.createRange();
            r.setStart(hintable, 0);
            const sel = doc.getSelection();
            sel.removeAllRanges();
            sel.addRange(r);
            break;
        }
    }

    *getHintables() {
        const hints = this.getResource("hints");
        const defaultHint = {
            selector: ".odoo-editor-editable .oe_structure,.odoo-editor-editable .o-paragraph",
        };
        const doc = this.document;
        let candidatePriority = () => true;
        if (this.editable.querySelector("article,.page")) {
            candidatePriority = (elem) => !!closestElement(elem, "article,.page");
        }
        const lowPriority = [];
        for (const hint of iterChain(hints, [defaultHint])) {
            for (const elem of doc.querySelectorAll(hint.selector)) {
                if (elem.innerText.trim() || !this.editable.contains(elem)) {
                    continue;
                }
                if (candidatePriority(elem)) {
                    const [deepest] = getDeepestPosition(elem, 0);
                    yield deepest || elem;
                } else {
                    lowPriority.push(elem);
                }
            }
        }
        yield* lowPriority;
    }

    getQwebVariable(element, qwebVariables, isInHeaderFooter) {
        const fullPath = element.getAttribute("t-field") || "";
        const qwebVar = fullPath.substring(0, fullPath.indexOf("."));
        if (qwebVar && qwebVar in qwebVariables) {
            return qwebVar;
        }

        if (isInHeaderFooter) {
            const companyVar = Object.entries(qwebVariables).find(
                ([k, v]) => v.model === "res.company"
            );
            return companyVar && companyVar[0];
        }

        const tAs = closestElement(element, "[t-foreach]")?.getAttribute("t-as");
        if (tAs) {
            return tAs;
        }

        const sortedVariables = this.getSortedVariables(qwebVariables, isInHeaderFooter);
        return (
            sortedVariables.find((varName) => ["doc", "o"].includes(varName)) ||
            sortedVariables.find((varName) => qwebVariables[varName].model === this.resModel)
        );
    }

    getSortedVariables(qwebVariables, isInHeaderFooter) {
        if (isInHeaderFooter) {
            return [];
        }

        const entries = Object.entries(qwebVariables).filter(([k, v]) => v.in_foreach);
        const sortFn = ([k, v]) => {
            let score = 0;
            if (k === "doc") {
                score += 2;
            }
            if (k === "docs") {
                score -= 2;
            }
            if (k === "o") {
                score++;
            }
            if (v.model === this.resModel) {
                score++;
            }
            return score;
        };

        return sortBy(entries, sortFn, "desc").map(([key]) => key);
    }

    onFieldApply(node) {
        const parentView = node.closest("[ws-view-id]");
        parentView.classList.add("o_dirty");
    }
}

class ColorUIPlugin extends _ColorUIPlugin {
    getPropsForColorSelector(...args) {
        const props = super.getPropsForColorSelector(...args);
        props.useDefaultThemeColors = false;
        return props;
    }
}

const EXCLUDED_PLUGIN_IDS = new Set(["powerButtons", "contrast"]);
const _PLUGINS = Object.fromEntries(
    [
        ...MAIN_PLUGINS.filter((cls) => !EXCLUDED_PLUGIN_IDS.has(cls.id)),
        ColorUIPlugin,
        QWebPlugin,
        QWebTablePlugin,
        ReportEditorPlugin,
    ].map((P) => [P.id, P])
);

export const REPORT_EDITOR_PLUGINS = Object.values(_PLUGINS);
