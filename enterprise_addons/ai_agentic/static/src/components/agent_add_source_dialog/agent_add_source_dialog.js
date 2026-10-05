import { Component, proxy, signal, t, useProps } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { useAutofocus, useService } from "@web/core/utils/hooks";
import { getDataURLFromFile } from "@web/core/utils/urls";
import { AiAgentPanelCard } from "@ai_agentic/components/ai_agent_panel_card/ai_agent_panel_card";

class AgentSourceURLDialog extends Component {
    static template = "ai.AgentSourceURLDialog";
    static components = {
        Dialog,
    };

    props = useProps({
        addURLSources: t.function(),
        close: t.function(),
    });
    autofocusRef = signal.ref();

    setup() {
        super.setup();
        useAutofocus({ ref: this.autofocusRef });
        this.state = proxy({
            urls: "",
        });
    }

    onConfirm() {
        this.props.addURLSources(this.state.urls);
        this.props.close();
    }
}

export class AgentSourceAddDialog extends Component {
    static template = "ai.AgentSourceAddDialog";
    static components = { AiAgentPanelCard, Dialog };

    props = useProps({
        agentId: t.number(),
        onSourcesAdded: t.function(),
        close: t.function(),
    });
    fileInputRef = signal.ref();

    setup() {
        super.setup();
        this.agentId = this.props.agentId;
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.actionService = useService("action");
        this.dialog = useService("dialog");
        this.state = proxy({
            loading: false,
        });
    }

    async onSourcesAdded() {
        await this.props.onSourcesAdded();
        this.props.close();
    }

    onAddFileSourceClick() {
        this.fileInputRef().click();
    }

    validateFileTypes(files) {
        const validFiles = [];
        const invalidFiles = [];
        for (const file of files) {
            const fileExtension = "." + file.name.split(".").pop().toLowerCase();
            if (this.allowedExtensions.includes(fileExtension)) {
                validFiles.push(file);
            } else {
                invalidFiles.push(file);
            }
        }

        return { validFiles, invalidFiles };
    }

    async addAttachmentSources(ev) {
        const files = ev.target.files;
        if (!files || !files.length) {
            return;
        }

        // Validate file types
        const { validFiles, invalidFiles } = this.validateFileTypes(Array.from(files));
        if (invalidFiles.length > 0 && validFiles.length > 0) {
            const invalidFileNames = invalidFiles.map((file) => file.name).join(", ");
            this.notification.add(
                _t(
                    "Some files have invalid formats and were skipped: %s. Only PDF, Word, PowerPoint, Excel, Text, CSV, and OpenDocument files are allowed.",
                    invalidFileNames
                ),
                {
                    type: "warning",
                }
            );
        }

        if (validFiles.length === 0) {
            this.notification.add(
                _t(
                    "No valid files to upload. Only PDF, Word, PowerPoint, Excel, Text, CSV, OpenDocument, and Markdown files are allowed."
                ),
                {
                    type: "danger",
                }
            );

            ev.target.value = "";
            return;
        }

        this.state.loading = true;
        try {
            const files_list = await Promise.all(
                validFiles.map(async (file) => ({
                    name: file.name,
                    raw: (await getDataURLFromFile(file)).split(",")[1],
                }))
            );
            const files_datas = [];
            for (const attachment_data of files_list) {
                files_datas.push({
                    name: attachment_data.name,
                    raw: attachment_data.raw,
                });
            }
            await this.orm.call("ai.agent.source", "create_from_binary_files", [
                files_datas,
                this.agentId,
            ]);
        } finally {
            this.state.loading = false;
            ev.target.value = "";
        }
        return this.onSourcesAdded();
    }

    onAddLinkSourceClick() {
        this.dialog.add(AgentSourceURLDialog, {
            addURLSources: async (urls_string) => await this.addURLSources(urls_string),
        });
    }

    validateAndFilterURLs(urls_list) {
        const validUrls = [];
        const invalidUrls = [];
        for (const url of urls_list) {
            if (
                url &&
                (url.startsWith("https://") ||
                    url.startsWith("http://") ||
                    url.startsWith("ftp://"))
            ) {
                validUrls.push(url);
            } else {
                invalidUrls.push(url);
            }
        }
        return { validUrls, invalidUrls };
    }

    async addURLSources(urls_string) {
        if (!urls_string) {
            return;
        }
        const urls_list = [
            ...new Set(
                urls_string
                    .split("\n")
                    .map((url) => url.trim())
                    .filter((url) => url !== "")
            ),
        ];

        if (urls_list.length > 0) {
            const { validUrls, invalidUrls } = this.validateAndFilterURLs(urls_list);
            if (validUrls.length > 0) {
                this.state.loading = true;
                try {
                    await this.orm.call("ai.agent.source", "create_from_urls", [
                        validUrls,
                        this.agentId,
                    ]);
                } finally {
                    this.state.loading = false;
                }
                if (invalidUrls.length > 0) {
                    this.notification.add(
                        _t(
                            "Some URLs are invalid and were skipped. URLs must start with http://, https://, or ftp://"
                        ),
                        {
                            type: "warning",
                        }
                    );
                }
                return this.onSourcesAdded();
            } else {
                this.notification.add(_t("No valid URLs found to process."), {
                    type: "danger",
                });
            }
        }
    }

    get cardsData() {
        return [
            {
                icon: "upload",
                title: _t("Upload a File"),
                onClick: () => this.onAddFileSourceClick(),
            },
            {
                icon: "link",
                title: _t("Add a Link"),
                onClick: () => this.onAddLinkSourceClick(),
            },
        ];
    }

    get allowedExtensions() {
        return [
            ".pdf",
            ".docx",
            ".doc",
            ".pptx",
            ".ppt",
            ".xlsx",
            ".xls",
            ".odt",
            ".ods",
            ".txt",
            ".csv",
            ".md",
        ];
    }
}
