import { registry } from "@web/core/registry";

function textLineIs(n, text) {
    return {
        trigger: `tr:nth-child(${n}) td:nth-child(2):text(${text})`,
    };
}

registry.category("web_tour.tours").add("account_reports_tour", {
    steps: () => [
        //--------------------------------------------------------------------------------------------------------------
        // Foldable
        //--------------------------------------------------------------------------------------------------------------
        {
            content: "Initial foldable",
            trigger: "table",
        },
        {
            trigger: `tbody > tr[data-id=line]:not(.o_hidden):not(.empty):count(26)`,
        },
        {
            content:
                "Since the total line is not displayed (folded), the amount should be on the line",
            trigger: `tr:nth-child(5) td:nth-child(2):text(75.00)`,

        },
        {
            content: "Click to unfold line",
            trigger: "tr:nth-child(5) td:first().unfoldable",
            run: "click",
        },
        {
            content: "Line is unfolded",
            trigger: "tr:nth-child(6) td:nth-child(1):contains('101401')",
        },
        {
            trigger: `tbody > tr[data-id=line]:not(.o_hidden):not(.empty):count(28)`,
        },
        {
            content:
                "Since the total line is displayed (unfolded), the amount should not be on the line",
            trigger: `tr:nth-child(5) td:nth-child(2):text()`,
        },
        {
            content: "Click to fold line",
            trigger: "tr:nth-child(5) td:first().unfoldable",
            run: "click",
        },
        {
            content: "Line is folded",
            trigger: "tr:nth-child(5) td:nth-child(2):text(75.00)",
        },
        {
            trigger: "tbody > tr[data-id=line]:not(.o_hidden):not(.empty):count(26)",
        },
        //--------------------------------------------------------------------------------------------------------------
        // Sortable
        //--------------------------------------------------------------------------------------------------------------
        {
            content: "Unfold first line",
            trigger: "tr:nth-child(5) td:first().unfoldable",
            run: "click",
        },
        {
            content: "Unfold second line",
            trigger: "tr:nth-child(8) td:first().unfoldable",
            run: "click",
        },
        {
            content: "Unfold third line",
            trigger: "tr:nth-child(11) td:first().unfoldable",
            run: "click",
        },
        {
            content: "Extra Trigger step",
            trigger: "tr:nth-child(13):not(.d-none) td:nth-child(1):contains('101404')",
        },
        {
            content: "Initial sortable",
            trigger: "tr:nth-child(12) td:nth-child(2):text(100.00)",
        },
        textLineIs(6, "75.00"),
        textLineIs(7, "75.00"),
        textLineIs(9, "25.00"),
        textLineIs(10, "25.00"),
        textLineIs(12, "100.00"),
        textLineIs(13, "50.00"),
        textLineIs(14, "150.00"),
        {
            content: "Click sort",
            trigger: "th .btn_sortable",
            run: "click",
        },
        {
            trigger: "tr:nth-child(12) td:nth-child(2):contains('50.00')",
        },
        {
            content: "Unfold not previously unfolded line",
            trigger: "tr:nth-child(23):contains('Current Liabilities') td:first().unfoldable",
            run: "click",
        },
        {
            content: "Line is unfolded",
            trigger: "tr:nth-child(24) td:nth-child(1):contains('251000')",
            run: "click",
        },
        textLineIs(6, "75.00"),
        textLineIs(7, "75.00"),
        textLineIs(9, "25.00"),
        textLineIs(10, "25.00"),
        textLineIs(12, "50.00"),
        textLineIs(13, "100.00"),
        textLineIs(14, "150.00"),
        {
            content: "Click sort",
            trigger: "th .btn_sortable",
            run: "click",
        },
        textLineIs(6, "75.00"),
        textLineIs(7, "75.00"),
        textLineIs(9, "25.00"),
        textLineIs(10, "25.00"),
        textLineIs(12, "100.00"),
        textLineIs(13, "50.00"),
        textLineIs(14, "150.00"),
        {
            content: "Click sort",
            trigger: "th .btn_sortable",
            run: "click",
        },
        textLineIs(6, "75.00"),
        textLineIs(7, "75.00"),
        textLineIs(9, "25.00"),
        textLineIs(10, "25.00"),
        textLineIs(12, "100.00"),
        textLineIs(13, "50.00"),
        textLineIs(14, "150.00"),
    ],
});

registry.category("web_tour.tours").add("account_reports_general_ledger_cumulated_balance", {
    steps: () => [
        {
            content: "Open the journal Items of the Bank account",
            trigger: "tr:has(td:nth-child(1):contains('4000')) .btn_action:contains('Journal Items'):not(:visible)",
            run: "click",
        },
        {
            content: "Open the optional columns dropdown",
            trigger: "div.o_optional_columns button",
            run: "click",
        },
        {
            content: "Check the cumulated balance column",
            trigger: ".o_popover span:has(input[name='cumulated_balance'])",
            run: "click",
        },
        {
            content: "Wait for the column to be visible",
            trigger: "th[data-name='cumulated_balance']:visible",
        },
        {
            content: "Check that the cumulated balance is correct on the move lines",
            trigger: ".o_list_table",
            run: async () => {
                const amounts = document.querySelectorAll("td[name='cumulated_balance']");
                const expectedAmounts = ["$ 30,000.00", "$ 29,000.00", "$ 27,500.00", "$ 25,500.00", "$ 23,000.00"];
                for (let i = 0; i < amounts.length; i++) {
                    if (amounts[i].textContent !== expectedAmounts[i]) {
                        throw new Error(`Expected cumulated balance to be ${expectedAmounts[i]}, but got ${amounts[i].textContent}`);
                    }
                }
                if (amounts.length !== expectedAmounts.length) {
                    throw new Error(`Expected ${expectedAmounts.length} cumulated balance cells, but got ${amounts.length}`);
                }
            },
        },
    ],
});
