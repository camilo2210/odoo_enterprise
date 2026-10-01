import { t, useProps } from "@odoo/owl";
import {
    ViewScaleSelector,
    viewScaleSelectorProps,
} from "@web/views/view_components/view_scale_selector";

export class GridScaleSelector extends ViewScaleSelector {
    props = useProps({
        ...viewScaleSelectorProps,
        isWeekendButtonDisabled: t.boolean().optional(),
    });

    get isWeekendButtonDisabled() {
        return super.isWeekendButtonDisabled || this.props.isWeekendButtonDisabled;
    }
}
