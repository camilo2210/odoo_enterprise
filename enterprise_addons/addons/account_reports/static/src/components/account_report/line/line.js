import { localization } from "@web/core/l10n/localization";

import { registry } from "@web/core/registry";
import { PopoverPlugin } from "@web/core/popover/popover_plugin";

import { Component, computed, signal, t, useEffect, usePlugin, useProps } from "@odoo/owl";

import { AccountReportController } from "@account_reports/components/account_report/controller";
import { AccountReportDebugPopover } from "@account_reports/components/account_report/line/popover/debug_popover";
import { AccountReportLineCellEditable } from "@account_reports/components/account_report/line_cell_editable/line_cell_editable";


export class AccountReportLine extends Component {
    static template = "account_reports.AccountReportLine";
    static components = {
        AccountReportLineCellEditable,
    };
    props = useProps({
        line: t.object(),
        lineIndex: t.signal(t.number()),
        virtualLineIndex: t.number(),
        numberOfVirtualLines: t.signal(t.number()),
    });

    controller = usePlugin(AccountReportController);
    popover = usePlugin(PopoverPlugin);

    lineRef = signal.ref();

    growthComparisonClasses = computed(() => this.getGrowthComparisonClasses());
    horizontalGroupTotalClasses = computed(() => this.getHorizontalGroupTotalClasses());
    shouldHide = computed(() => this.props.virtualLineIndex >= this.props.numberOfVirtualLines());
    hasComparisonData = computed(() => Boolean(this.props.line.column_percent_comparison_data?.figure_type()));
    hasDebugData = computed(() => Boolean(this.props.line.debug_popup_data?.()));
    isLevel0 = computed(() => this.props.line.level() === 0);

    lineClasses = "";

    setup() {
        useEffect(() => {
            const classes = this.getLineClasses();
            if (classes === this.lineClasses) return;

            const prevLineClasses = this.lineClasses;
            this.lineClasses = classes;
            const prev = prevLineClasses ? prevLineClasses.trim().split(/\s+/).filter(Boolean) : [];
            const next = classes ? classes.trim().split(/\s+/).filter(Boolean) : [];
            this.controller.scheduleClassUpdate(this.lineRef, prev, next);
        });
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Line
    // -----------------------------------------------------------------------------------------------------------------
    getLineClasses() {
        const line = this.props.line;
        let classes = "level" in line ? `line_level_${line.level()}` : "line_level_default";

        if (line.unfolded?.() && this.hasVisibleChild())
            classes += " unfolded";

        if (this.controller.isTotalLine(line.id()))
            classes += " total";

        if (line.css_class?.())
            classes += ` ${line.css_class()}`;

        return classes;
    }

    hasVisibleChild() {
        if (!this.controller.data()) return false;
        let nextLineIndex = this.props.lineIndex() + 1;

        while (this.controller.isNextLineChild(nextLineIndex, this.props.line.id())) {
            if (this.controller.lines[nextLineIndex].visible && this.controller.lines[nextLineIndex].search_match !== false)
                return true;

            nextLineIndex += 1;
        }
        return false;
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Growth comparison
    // -----------------------------------------------------------------------------------------------------------------
    getGrowthComparisonClasses() {
        let classes = "text-end fw-bold";

        switch (this.props.line.column_percent_comparison_data.comparison_mode?.()) {
            case "green":
                classes += " text-success";
                break;
            case "muted":
                classes += " muted";
                break;
            case "red":
                classes += " text-danger";
                break;
        }

        return classes;
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Total Horizontal Group
    // -----------------------------------------------------------------------------------------------------------------
    getHorizontalGroupTotalClasses() {
        let classes = "text-end";
        switch (Math.sign(this.props.line.horizontal_group_total_data?.no_format())) {
            case 1:
                break;
            case 0:
                classes += " muted";
                break;
            case -1:
                classes += " text-danger";
                break;
        }

        return classes;
    }

    //------------------------------------------------------------------------------------------------------------------
    // Debug popover
    //------------------------------------------------------------------------------------------------------------------
    showDebugPopover(ev) {
        const close = () => {
            this.popoverCloseFn();
            this.popoverCloseFn = null;
        };

        if (this.popoverCloseFn)
            close();

        this.popoverCloseFn = this.popover.add(
            ev.currentTarget,
            AccountReportDebugPopover,
            {
                expressionsDetail: JSON.parse(this.props.line.debug_popup_data()).expressions_detail,
                onClose: close,
            },
            {
                closeOnClickAway: true,
                position: localization.direction === "rtl" ? "left" : "right",
            },
        );
    }

    //------------------------------------------------------------------------------------------------------------------
    // Virtual Grid
    //------------------------------------------------------------------------------------------------------------------
    /** Return the height of a *stored* line in pixels.
     * 
     * If you are adding a custom line and this line is higher than normal line, you will need to override this function.
     * Make sure to check if it's 0 first, as this function also checks if a line is visible or not.
     * 
     * @param {AccountReportController} controller 
     * @param {'left' | 'right'} side The side of the horizontal split we want to know the line is on
     * @param {Object} line
     * @param {number} normalLineHeight The height in px of a rendered line without anything except some text
     * @param {Record<string, number | undefined>} customClassesHeights A map of css_class to their height which were rendered using
     *  some text and the css_class on the tr.
     */
    static getLineHeight(controller, side, line, normalLineHeight) {
        if (line.visible === false) return 0;
        if (line.search_match === false) return 0;
        if (controller.options().horizontal_split && line.horizontal_split_side !== side) return 0;
        
        let height = normalLineHeight;
        if (line.level === 0) {  // since an empty line is added above the line
            height += normalLineHeight;
        }
        return height;
    }
}

registry.category("account_reports.default_components").add("AccountReportLine", AccountReportLine);
