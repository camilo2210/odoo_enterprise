import { Component, t, useProps } from "@odoo/owl";

export class NewContentRefreshBanner extends Component {
    static template = "social.NewContentRefreshBanner";

    props = useProps({
        refreshRequired: t.any(),
        onClickRefresh: t.any(),
    });
}
