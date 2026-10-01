import { registry } from "@web/core/registry";

const makeTextFile = ({ name, mime, content }) => new File([content], name, { type: mime });

const setFileOnInput = (inputEl, file) => {
    const dt = new DataTransfer();
    dt.items.add(file);
    inputEl.files = dt.files;
    inputEl.dispatchEvent(new Event("change", { bubbles: true }));
};

const getXMLVendorBillDemo = async () => {
    const url = "/documents_account/static/tests/assets/demo_vendor_bill.xml";
    const res = await fetch(url);
    if (!res.ok) {
        throw new Error(`Error while loading the vendor bill : (${res.status})`);
    }
    return (await res.text()).trim();
};

registry.category("web_tour.tours").add("test_embedded_pdf_thumbnail_generation", {
    steps: () => [
        {
            content: "Open Documents app",
            trigger: '.o_app[data-menu-xmlid="documents.menu_root"]',
            run: "click",
        },
        {
            content: "Wait for documents view",
            trigger: ".o_documents_kanban, .o_documents_view",
        },
        {
            content: "Upload XML file containing embedded PDF",
            trigger: 'input[type="file"]:not(:visible)',
            run: async function () {
                const inputEl = document.querySelector('input[type="file"]');
                if (!inputEl) {
                    throw new Error("No file input found for upload");
                }

                const vendorBillExample = await getXMLVendorBillDemo();
                const file = makeTextFile({
                    name: "demo_vendor_bill.xml",
                    mime: "text/xml",
                    content: vendorBillExample,
                });

                setFileOnInput(inputEl, file);
            },
        },
        // ensure that an image thumbnail is eventually generated for the imported vendor bill
        {
            content: "Wait for uploaded document card",
            trigger:
                '.o_kanban_record:contains("demo_vendor_bill.xml") img[alt="Document preview"]',
        },
    ],
});
