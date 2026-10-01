import { Domain } from "@web/core/domain";
import { user } from "@web/core/user";

import "@documents/../tests/mock_server/controllers/documents";
import "@documents/../tests/mock_server/mock_models/ir_attachment";
import { makeDocumentRecordData } from "@documents/../tests/helpers/document_data";
import { mailModels } from "@mail/../tests/mail_test_helpers";
import { fields, models, serverState, webModels } from "@web/../tests/web_test_helpers";

export class DocumentsDocument extends models.ServerModel {
    _name = "documents.document";
    _parent_name = "folder_id";

    access_internal = fields.Selection({
        selection: [
            ["edit", "Editor"],
            ["view", "Viewer"],
            ["none", "None"],
        ],
        default: "edit",
    });
    access_via_link = fields.Selection({
        selection: [
            ["edit", "Editor"],
            ["view", "Viewer"],
            ["none", "None"],
        ],
        default: "none",
    });
    is_access_via_link_hidden = fields.Boolean();

    activity_state = fields.Selection({
        selection: [
            ["overdue", "Overdue"],
            ["today", "Today"],
            ["planned", "Planned"],
        ],
        readonly: true,
        store: false,
    });
    name = fields.Char();
    thumbnail = fields.Binary();
    favorited_ids = fields.Many2many({ relation: "res.users" });
    is_favorited = fields.Boolean({ store: false });
    is_folder = fields.Boolean({ readonly: true, store: false }); // used for ordering
    is_multipage = fields.Boolean();

    user_can_move = fields.Boolean({ default: true });
    is_editable_attachment = fields.Boolean();
    mimetype = fields.Char({ readonly: true, store: false });
    partner_id = fields.Many2one({ relation: "res.partner" });
    owner_id = fields.Many2one({ relation: "res.users" });
    previous_attachment_ids = fields.Many2many({ relation: "ir.attachment" });
    tag_ids = fields.Many2many({ relation: "documents.tag" });
    folder_id = fields.Many2one({ relation: "documents.document" });
    user_folder_id = fields.Char({ readonly: true, store: false });
    res_model = fields.Char();
    attachment_id = fields.Many2one({ relation: "ir.attachment" });
    company_id = fields.Many2one({ relation: "res.company" });
    active = fields.Boolean({ default: true });
    activity_ids = fields.One2many({ relation: "mail.activity" });
    my_activity_date_deadline = fields.Date({ readonly: true, store: false });
    checksum = fields.Char({ readonly: true, store: false });
    file_extension = fields.Char();
    thumbnail_status = fields.Selection({
        selection: [
            ["present", "Present"],
            ["error", "Error"],
            ["client_generated", "Client Generated"],
        ],
    });
    lock_uid = fields.Many2one({ relation: "res.users" });
    message_attachment_count = fields.Integer({ readonly: true, store: false });
    message_follower_ids = fields.One2many({ relation: "mail.followers" });
    message_ids = fields.One2many({ relation: "mail.message" });
    res_id = fields.Many2oneReference({ model_field: "res_model" });
    res_name = fields.Char({ readonly: true, store: false });
    res_model_name = fields.Char({ readonly: true, store: false });
    type = fields.Selection({
        selection: [
            ["binary", "File"],
            ["url", "Url"],
            ["folder", "Folder"],
        ],
        default: "binary",
    });
    shortcut_document_id = fields.Many2one({ relation: "documents.document" });
    url = fields.Char();
    url_preview_image = fields.Char();
    file_size = fields.Integer({ readonly: true });
    raw = fields.Binary({ store: false });
    access_token = fields.Char({ readonly: true, store: false });
    user_permission = fields.Selection({
        selection: [
            ["edit", "Editor"],
            ["view", "Viewer"],
            ["none", "None"],
        ],
        default: "edit",
    });
    is_protected = fields.Boolean({ readonly: true, store: false });
    available_embedded_actions_ids = fields.Many2many({
        relation: "ir.embedded.actions",
        readonly: true,
        store: false,
    });
    alias_id = fields.Many2one({ relation: "mail.alias" });
    alias_domain_id = fields.Many2one({ relation: "mail.alias.domain", store: false });
    alias_name = fields.Char({ store: false });
    alias_tag_ids = fields.Many2many({ relation: "documents.tag" });
    mail_alias_domain_count = fields.Integer({ readonly: true, store: false });
    create_activity_type_id = fields.Many2one({ relation: "mail.activity.type" });
    create_activity_user_id = fields.Many2one({ relation: "res.users" });
    description = fields.Text({ store: false });
    last_access_date_group = fields.Selection({
        selection: [
            ["0_older", "Older"],
            ["1_month", "This Month"],
            ["2_week", "This Week"],
            ["3_day", "Today"],
        ],
        default: "3_day",
    });
    activity_user_id = fields.Many2one({ relation: "res.users", readonly: true, store: false });
    // added here for convenience, do not use in views if the field does not exist (as in "base" `documents`)
    has_embedded_pdf = fields.Boolean({ string: "Has Embedded PDF" });

    get_deletion_delay() {
        return 30;
    }

    get_document_max_upload_limit() {
        return 67000000;
    }

    get_details_panel_res_models() {
        // Nine elements to match the number actually sent by the server when all apps are present.
        return [
            "res.partner",
            "res.users",
            "mail.activity",
            "mail.activity.type",
            "mail.channel",
            "mail.channel.member",
            "mail.channel.message",
            "mail.message",
            "documents.document",
        ];
    }

    action_create_shortcut() {
        return;
    }

    /**
     * Override to implement _search_user_folder_id search method, and to hide
     * the documents the user has no access to (as the record rules do).
     */
    web_search_read() {
        const kwargs = arguments[0];
        const domain = kwargs?.domain;
        if (domain) {
            const folderLeafIdx = domain.findIndex((leaf) => leaf[0] === "user_folder_id");
            if (folderLeafIdx !== -1) {
                domain.splice(folderLeafIdx, 1, [
                    "user_folder_id",
                    domain[folderLeafIdx][1],
                    domain[folderLeafIdx][2].toString(),
                ]);
            }
            // maybe redundant but should never be incorrect
            kwargs.domain = Domain.and([domain, [["user_permission", "!=", "none"]]]).toList();
        } else {
            kwargs.domain = [["user_permission", "!=", "none"]];
        }
        return super.web_search_read(...arguments);
    }

    action_move_folder(folder, target, before_folder_id = false) {
        const record = this.filter((r) => folder.id === r.id);
        record.folder_id = target;
    }

    /**
     * @override to avoid super() not working for us.
     * Folders the user has no access to are not returned, as on the server.
     */
    async search_panel_select_range(fieldName) {
        const result = { parent_field: "user_folder_id" };
        result.values = await this._get_search_panel_specials();
        for (const record of this.search_read(
            [
                ["type", "=", "folder"],
                ["user_permission", "!=", "none"],
            ],
            [
                "access_internal",
                "access_via_link",
                "active",
                "alias_domain_id",
                "alias_name",
                "alias_tag_ids",
                "company_id",
                "create_activity_type_id",
                "description",
                "display_name",
                "user_folder_id",
                "id",
                "is_access_via_link_hidden",
                "is_folder",
                "mail_alias_domain_count",
                "owner_id",
                "partner_id",
                "type",
                "user_permission",
                "access_token",
            ]
        )) {
            if (!isNaN(record.user_folder_id)) {
                record.user_folder_id = Number(record.user_folder_id);
            }
            if (!record.active) {
                record.user_folder_id = "TRASH";
            }
            if (record.alias_tag_ids) {
                record.alias_tag_ids = record.alias_tag_ids.map((id) => {
                    const [tag] = this.env["documents.tag"].browse(id);
                    return { id, color: tag.color, display_name: tag.name };
                });
            }
            result.values.push(record);
        }
        return result;
    }

    async _get_search_panel_specials() {
        if (!(await user.hasGroup("base.group_user"))) {
            return [];
        }
        return [
            {
                bold: true,
                childrenIds: [],
                parentId: false,
                user_permission: "view",
                display_name: "Company",
                id: "COMPANY",
                description: "Common roots for all company users.",
            },
            {
                bold: true,
                childrenIds: [],
                parentId: false,
                user_permission: "edit",
                display_name: "My Drive",
                id: "MY",
                description: "Your individual space.",
            },
            {
                bold: true,
                childrenIds: [],
                parentId: false,
                user_permission: "edit",
                display_name: "Shared with me",
                id: "SHARED",
                description: "Additional documents you have access to.",
            },
            {
                bold: true,
                childrenIds: [],
                parentId: false,
                user_permission: "edit",
                display_name: "Recent",
                id: "RECENT",
                description: "Recently accessed documents.",
            },
            {
                bold: true,
                childrenIds: [],
                parentId: false,
                user_permission: "edit",
                display_name: "Trash",
                id: "TRASH",
                description: "Items in trash will be deleted forever after 30 days.",
            },
        ];
    }

    toggle_lock(id) {
        const record = this.browse(id)[0];
        record.lock_uid = record.lock_uid ? false : serverState.odoobotId;
    }

    get_documents_actions(folder_id) {
        return [];
    }

    _store_document_fields(res) {
        res.attr("name");
        res.attr("user_can_move");
        res.attr("user_folder_id");
        res.one("folder_id", ["display_name"]);
        res.one("attachment_id", []);
    }
}

export class DocumentsOperation extends models.Model {
    _name = "documents.operation";

    operation = fields.Selection({
        selection: [
            ["move", "Move"],
            ["shortcut", "Create shortcuts"],
            ["copy", "Duplicate to"],
            ["add", "Add attachment to Documents"],
        ],
    });
    document_ids = fields.Many2many({ relation: "documents.document" });
    attachment_id = fields.Many2one({ relation: "ir.attachment" });

    destination = fields.Char({ default: "MY" });
    display_name = fields.Char({ default: "My Drive" });

    user_permission = fields.Char({ string: "Destination User Permission", default: "edit" });
    access_internal = fields.Char({ string: "Destination Access Internal", default: "edit" });
    access_via_link = fields.Char({ string: "Destination Access Via Link", default: "edit" });
    is_access_via_link_hidden = fields.Boolean({ string: "Destination Link Access Hidden" });

    get_any_editor_destination() {
        for (const record of this.env["documents.document"].search_read(
            [["type", "=", "folder"]],
            ["shortcut_document_id", "type", "user_permission"]
        )) {
            if (
                record.type === "folder" &&
                !record.shortcut_document_id &&
                record.user_permission === "edit"
            ) {
                return [{ destination: record.id.toString(), display_name: record.display_name }];
            }
        }
        return [];
    }
}

export class DocumentsTag extends models.ServerModel {
    _name = "documents.tag";

    color = fields.Integer({ default: 1 });
    sequence = fields.Integer({ default: 10 });
}

export class DocumentsSharing extends models.Model {
    _name = "documents.sharing";

    access_internal = fields.Selection({
        selection: [
            ["edit", "Editor"],
            ["write_edit", "Editor"],
            ["view", "Viewer"],
            ["write_view", "Viewer"],
            ["none", "None"],
            ["write_none", "None"],
            ["mixed", "Mixed rights"],
        ],
    });
}

/**
 * @returns {Object}
 */
export function getDocumentsTestServerModelsData(additionalRecords = []) {
    return {
        "res.users": [
            { name: "OdooBot", id: serverState.odoobotId },
            {
                name: serverState.partnerName,
                id: serverState.userId,
                active: true,
                partner_id: serverState.partnerId,
            },
        ],
        "documents.document": [
            makeDocumentRecordData(1, "Folder 1", { type: "folder", user_permission: "edit" }),
            ...additionalRecords,
        ],
        "documents.tag": [
            {
                id: 1,
                name: "Colorless",
                color: 0,
            },
            {
                id: 2,
                name: "Colorful",
                color: 1,
            },
        ],
        "mail.alias": [
            {
                id: 1,
                alias_domain_id: 1,
                alias_name: "alias",
            },
        ],

        "mail.alias.domain": [
            {
                id: 1,
                name: "odoo.com",
            },
            {
                id: 2,
                name: "runbot.odoo.com",
            },
        ],

        "res.company": serverState.companies,
    };
}

export const DocumentsModels = {
    ...mailModels,
    ResCompany: webModels.ResCompany,
    DocumentsDocument,
    DocumentsOperation,
    DocumentsTag,
    DocumentsSharing,
};

export function getDocumentsModel(modelName) {
    return Object.values(DocumentsModels).find((model) => model.getModelName() === modelName);
}

export const mimetypeExamplesBase64 = {
    WEBP: "UklGRjoAAABXRUJQVlA4IC4AAAAwAQCdASoBAAEAAUAmJaAAA3AA/u/uY//8s//2W/7LeM///5Bj/dl/pJxGAAAA",
};

export { makeDocumentRecordData };
