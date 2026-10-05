import { t, useProps } from "@odoo/owl";
import { MapModel } from "@web_map/map_view/map_model";
import { MapPopover } from "@web_map/map_view/map_popover";
import { usePlanningPopoverFooter } from "@planning/components/planning_popover_footer/planning_popover_footer";

// Exported so overriding modules can extend the schema: they add buttons to the
// footer template, and the props those buttons read must be declared here.
export const planningFieldServiceMapPopoverProps = {
    close: t.function(),
    model: t.instanceOf(MapModel),
    resIds: t.array(),
    record: t.object(),
    openRecord: t.function().optional(),
    reloadOnClose: t.function().optional(),
    onStart: t.function().optional(),
    onComplete: t.function().optional(),
    onNavigate: t.function().optional(),
    onUnschedule: t.function().optional(),
    onDelete: t.function().optional(),
};

export class PlanningFieldServiceMapPopover extends MapPopover {
    static defaultFooterButtonsTemplate =
        "planning_field_service.PlanningFieldServiceMapPopover.DefaultFooterButtons";
    props = useProps(planningFieldServiceMapPopoverProps);

    setup() {
        super.setup();
        this.footer = usePlanningPopoverFooter(() => this.props.close());
    }

    get readonly() {
        return !this.props.record.can_edit;
    }
}
