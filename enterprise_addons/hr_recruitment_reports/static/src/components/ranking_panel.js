import { Component, t, useProps } from "@odoo/owl";

export default class RankingPanel extends Component {
    static template = "hr_recruitment_reports.RankingPanel";

    props = useProps({
        ranked_list: t.object(),
    });
}
