export const belgiumAdditionalPersonalInfo = () => [
    {
        content: "Language",
        trigger: "select[name=lang]:not(:visible)",
        run: "selectByLabel English",
    },
    {
        content: "Account Holder Name",
        trigger: 'input[name="holder_name"]',
        run: "edit Mohamed Dallash"
    },
    {
        content: "Upload ID card copy (Both Sides)",
        trigger: 'input[name="id_card"]',
        async run({ inputFiles }) {
            const file = new File(["hello, world"], "employee_id_card.pdf", {
                type: "application/pdf",
            });
            await inputFiles('input[name="id_card"]', [file]);
        },
    },
    {
        content: "Select Mobile Subscription (30.0 €)",
        trigger: 'label:has(input[type="radio"][name="mobile_radio"][data-value="30.0"])',
        run: "click",
    },
    {
        content: "Upload Mobile Subscription Invoice",
        trigger: 'input[name="mobile_invoice"]',
        async run({ inputFiles }) {
            const file = new File(["hello, world"], "employee_mobile_invoice.pdf", {
                type: "application/pdf",
            });

            await inputFiles('input[name="mobile_invoice"]', [file]);
        },
    },
    {
        content: "Upload Sim Card Copy",
        trigger: 'input[name="sim_card"]',
        async run({ inputFiles }) {
            const file = new File(["hello, world"], "employee_sim_card.pdf", {
                type: "application/pdf",
            });

            await inputFiles('input[name="sim_card"]', [file]);
        },
    },
    {
        content: "Set Internet",
        trigger: 'input[name="internet_manual"]',
        run: "edit 38 && click label:contains(Internet)",
    },
    {
        content: "Upload Internet Subscription invoice",
        trigger: 'input[name="internet_invoice"]',
        async run({ inputFiles }) {
            const file = new File(["hello, world"], "employee_internet_invoice.pdf", {
                type: "application/pdf",
            });
            await inputFiles('input[name="internet_invoice"]', [file]);
        },
    },
];
