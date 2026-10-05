import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("import_fec_file_tour", {
    steps: () => [
        {
            content: "Import FEC wizard",
            trigger: 'button:contains("Import FEC")',
            run: "click",
        },
        {
            content: "Upload FEC file",
            trigger: 'button:contains("Upload")',
            async run({ inputFiles }) {
                const response = await fetch(
                    "/l10n_fr_fec_import/static/tests/fec_test_files/fec_lf_tab_utf8.txt"
                );
                const fileText = await response.text();
                const file = new File([fileText], "fec_file.txt", { type: "text/plain" });
                await inputFiles("input.o_input_file", [file]);
            },
        },
        {
            content: "Process imported file",
            trigger: 'footer button:contains("Import")',
            run: "click",
        },
        {
            content: "Import Succeeded",
            trigger: ".o_import_summary",
        },
    ],
});
