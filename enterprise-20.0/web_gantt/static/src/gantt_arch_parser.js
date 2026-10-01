import { formatLocalWeekRange } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
import { evaluateExpr } from "@web/core/py_js/py";
import { omit } from "@web/core/utils/objects";
import { exprToBoolean } from "@web/core/utils/strings";
import { visitXML } from "@web/core/utils/xml";
import { getActiveActions } from "@web/views/utils";
import { diffColumn } from "./gantt_helpers";

const DECORATIONS = [
    "decoration-danger",
    "decoration-info",
    "decoration-secondary",
    "decoration-success",
    "decoration-warning",
];
const PARTS = { full: 1, half: 2, quarter: 4 };
const SCALES = {
    day: {
        // determines subcolumns
        cellPrecisions: { full: 60, half: 30, quarter: 15 },
        defaultPrecision: "full",
        time: "minute",
        unitDescription: _t("minutes"),

        // determines columns
        interval: "hour",
        minimalColumnWidth: 40,
        colHeaderTitle: (date) => date.toFormat("DDDD, t"),

        // determines column groups
        unit: "day",
        groupHeaderFormatter: (date) => date.toFormat("DDDD"),
        groupHeaderTitle: (date) => date.toFormat("DDDD"),
    },
    week: {
        cellPrecisions: { full: 24, half: 12, quarter: 6 },
        defaultPrecision: "half",
        time: "hour",
        unitDescription: _t("hours"),

        interval: "day",
        minimalColumnWidth: 192,
        colHeaderFormatter: (date) => date.toFormat("cccc d"),
        colHeaderTitle: (date) => date.toFormat("DDDD"),

        unit: "week",
        groupHeaderFormatter: formatLocalWeekRange,
        groupHeaderTitle: formatLocalWeekRange,
    },
    month: {
        cellPrecisions: { full: 24, half: 12, quarter: 6 },
        defaultPrecision: "half",
        time: "hour",
        unitDescription: _t("hours"),

        interval: "day",
        minimalColumnWidth: 52,
        colHeaderFormatter: (date) => date.toFormat("dd"),
        colHeaderTitle: (date) => date.toFormat("DDDD"),

        unit: "month",
        groupHeaderFormatter: (date, env) =>
            date.toFormat(env.services.ui.isSmall ? "MMM yyyy" : "MMMM yyyy"),
        groupHeaderTitle: (date, env) =>
            date.toFormat(env.services.ui.isSmall ? "MMM yyyy" : "MMMM yyyy"),
    },
    year: {
        cellPrecisions: { full: 1 },
        defaultPrecision: "full",
        time: "month",
        unitDescription: _t("months"),

        interval: "month",
        minimalColumnWidth: 100,
        colHeaderFormatter: (date, env) => date.toFormat(env.services.ui.isSmall ? "MMM" : "MMMM"),
        colHeaderTitle: (date, env) =>
            date.toFormat(env.services.ui.isSmall ? "MMM yyyy" : "MMMM yyyy"),

        unit: "year",
        groupHeaderFormatter: (date) => date.toFormat("yyyy"),
        groupHeaderTitle: (date) => date.toFormat("yyyy"),
    },
};
const RESCHEDULE_METHODS = {
    manual: "Manual Reschedule",
    consumeBuffer: "Auto-Reschedule (Use Buffer)",
    maintainBuffer: "Auto-Reschedule (Keep Buffer)",
};

function getPreferedScaleId(scaleId, scales) {
    // we assume that scales is not empty
    if (scaleId in scales) {
        return scaleId;
    }
    const scaleIds = Object.keys(SCALES);
    const index = scaleIds.findIndex((id) => id === scaleId);
    for (let j = index - 1; j >= 0; j--) {
        const id = scaleIds[j];
        if (id in scales) {
            return id;
        }
    }
    for (let j = index + 1; j < scaleIds.length; j++) {
        const id = scaleIds[j];
        if (id in scales) {
            return id;
        }
    }
}

export function getScaleForCustomRange(params) {
    const { scales, startDate, stopDate } = params;
    const lengthInDays = diffColumn(startDate, stopDate, "day");
    let unit;
    if (lengthInDays < 6) {
        unit = "day";
    } else if (lengthInDays < 27) {
        unit = "week";
    } else if (lengthInDays < 364) {
        unit = "month";
    } else {
        unit = "year";
    }
    const scaleId = getPreferedScaleId(unit, scales);
    return scales[scaleId];
}

const RANGES = {
    day: { scaleId: "day", description: _t("Day") },
    week: { scaleId: "week", description: _t("Week") },
    month: { scaleId: "month", description: _t("Month") },
    quarter: { scaleId: "month", description: _t("Quarter") },
    year: { scaleId: "year", description: _t("Year") },
};

export class GanttArchParser {
    parse(arch) {
        let infoFromRootNode;
        const decorationFields = [];
        let popoverNode;

        visitXML(arch, (node) => {
            switch (node.tagName) {
                case "gantt": {
                    infoFromRootNode = getInfoFromRootNode(node);
                    break;
                }
                case "field": {
                    decorationFields.push(node.getAttribute("name"));
                    break;
                }
                case "popover": {
                    popoverNode = node;
                    return false;
                }
            }
        });

        return {
            ...infoFromRootNode,
            decorationFields,
            popoverNode,
        };
    }
}

function getInfoFromRootNode(rootNode) {
    const attrs = {};
    for (const { name, value } of rootNode.attributes) {
        attrs[name] = value;
    }

    const { create: canCreate, delete: canDelete, edit: canEdit } = getActiveActions(rootNode);
    const canCellCreate = exprToBoolean(attrs.cell_create, true) && canCreate;
    const canPlan = exprToBoolean(attrs.plan, true) && canEdit;

    const dependencyField = attrs.dependency_field || null;
    const dependencyEnabled = !!dependencyField;
    const dependencyInvertedField = attrs.dependency_inverted_field || null;

    const allowedRanges = new Set();
    if (attrs.scales) {
        for (const key of attrs.scales.split(",")) {
            if (RANGES[key]) {
                allowedRanges.add(key);
            }
        }
    }
    if (allowedRanges.size === 0) {
        for (const rangeId in RANGES) {
            allowedRanges.add(rangeId);
        }
    }

    let defaultRange = attrs.default_range || attrs.default_scale;
    if (defaultRange && RANGES[defaultRange]) {
        if (!allowedRanges.has(defaultRange)) {
            allowedRanges.add(defaultRange);
        }
    } else {
        defaultRange = "custom";
    }

    // Cell precision
    const cellPrecisions = {};

    // precision = {'day': 'hour:half', 'week': 'day:half', 'month': 'day', 'year': 'month:quarter'}
    const precisionAttrs = attrs.precision ? evaluateExpr(attrs.precision) : {};
    for (const scaleId in SCALES) {
        if (precisionAttrs[scaleId]) {
            const precision = precisionAttrs[scaleId].split(":"); // hour:half
            // Note that precision[0] (which is the cell interval) is not
            // taken into account right now because it is no customizable.
            if (
                precision[1] &&
                Object.keys(SCALES[scaleId].cellPrecisions).includes(precision[1])
            ) {
                cellPrecisions[scaleId] = precision[1];
            }
        }
        cellPrecisions[scaleId] ||= SCALES[scaleId].defaultPrecision;
    }

    function getScale(scaleId) {
        const precision = cellPrecisions[scaleId];
        const referenceScale = SCALES[scaleId];
        return {
            ...omit(referenceScale, "cellPrecisions"),
            cellPart: PARTS[precision],
            cellTime: referenceScale.cellPrecisions[precision],
            id: scaleId,
            unitDescription: referenceScale.unitDescription.toString(),
        };
    }

    const scales = {};
    const ranges = {};
    for (const rangeId in RANGES) {
        if (!allowedRanges.has(rangeId)) {
            continue;
        }
        const { scaleId, description } = RANGES[rangeId];
        ranges[rangeId] = {
            scaleId,
            id: rangeId,
            description: description.toString(),
        };
        scales[rangeId] = getScale(scaleId);
    }

    let pillDecorations = null;
    for (const decoration of DECORATIONS) {
        if (decoration in attrs) {
            if (!pillDecorations) {
                pillDecorations = {};
            }
            pillDecorations[decoration] = attrs[decoration];
        }
    }

    return {
        bufferStartField: attrs.buffer_start,
        bufferStopField: attrs.buffer_stop,
        canCellCreate,
        canCreate,
        canDelete,
        canEdit,
        canPlan,
        canSchedule: exprToBoolean(attrs.schedule, false),
        colorField: attrs.color,
        computePillDisplayName: !!attrs.pill_label,
        createAction: attrs.on_create || null,
        dateStartField: attrs.date_start,
        dateStopField: attrs.date_stop,
        defaultRange,
        dependencyEnabled,
        dependencyField,
        dependencyInvertedField,
        disableDrag: exprToBoolean(attrs.disable_drag_drop),
        displayMode: attrs.display_mode || "dense",
        displayTotalRow: exprToBoolean(attrs.total_row),
        displayUnavailability: exprToBoolean(attrs.display_unavailability),
        formViewId: attrs.form_view_id ? parseInt(attrs.form_view_id, 10) : false,
        multiCreateView: attrs.multi_create_view || null,
        pagerLimit: attrs.groups_limit ? parseInt(attrs.groups_limit, 10) : null,
        pillDecorations,
        progressBarFields: attrs.progress_bar ? attrs.progress_bar.split(",") : null,
        progressField: attrs.progress || null,
        ranges,
        scales,
        string: attrs.string || _t("Gantt View").toString(),
        thumbnails: attrs.thumbnails ? evaluateExpr(attrs.thumbnails) : {},
        rescheduleMethods: RESCHEDULE_METHODS,
        defaultRescheduleMethod: "maintainBuffer",
    };
}
