import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("account_reports_load_more", {
    steps: () => [
        /*
          When opening the report:
          - 1 partner is shown
          - 2 more in "load more"
          - All lines are folded, first partner has 2 move lines to report, when unfolded (with a "1 more" after the first unfold)
        */
        {
            content: "Check default-loaded lines",
            trigger: "tr:nth-child(2) td:nth-child(1)",
        },
        {
            trigger: `tr:nth-child(3) td:nth-child(1):contains(partner_a)`,
        },
        {
            content: "Unfold first partner",
            trigger: "tr:nth-child(3) td:first().unfoldable",
            run: "click",
        },
        {
            content: "First partner should be unfolded",
            trigger: "tr td:nth-child(1):contains('INV/2016/00001')",
        },
        {
            trigger: `tr:nth-child(3) td:nth-child(1):contains(partner_a)`,
        },
        {
            trigger: `tr:nth-child(4) td:nth-child(1):contains(INV/2016/00001)`,
        },
        {
            trigger: `tr:nth-child(5) td:nth-child(1) a:text(1 more)`,
        },
        {
            trigger: `tr:nth-child(6) td:nth-child(1):contains(Total partner_a)`,
        },
        {
            trigger: `tr:nth-child(7) td:nth-child(1) a:text(2 more)`,
        },
        {
            content: "Load more the first partner's move",
            trigger: "a:text('1 more')",
            run: "click",
        },
        {
            trigger: `tr:nth-child(3) td:nth-child(1):contains(partner_a)`,
        },
        {
            trigger: `tr:nth-child(4) td:nth-child(1):contains(INV/2016/00002)`,
        },
        {
            trigger: `tr:nth-child(5) td:nth-child(1):contains(INV/2016/00001)`,
        },
        {
            trigger: `tr:nth-child(6) td:nth-child(1):contains(Total partner_a)`,
        },
        {
            trigger: `tr:nth-child(7) td:nth-child(1) a:text(2 more)`,
        },
        {
            content: "Load more the other partners",
            trigger: "a:text('2 more')",
            run: "click",
        },
        {
            content:
                "All partners should be shown ; the expanded and loaded lines from partner 1 should still be there",
            trigger: "tr td:nth-child(1):contains('partner_c')",
        },
        {
            trigger: `tr:nth-child(3) td:nth-child(1):contains(partner_a)`,
        },
        {
            trigger: `tr:nth-child(4) td:nth-child(1):contains(INV/2016/00002)`,
        },
        {
            trigger: `tr:nth-child(5) td:nth-child(1):contains(INV/2016/00001)`,
        },
        {
            trigger: `tr:nth-child(6) td:nth-child(1):contains(Total partner_a)`,
        },
        {
            trigger: `tr:nth-child(7) td:nth-child(1):contains(partner_b)`,
        },
    ],
});
