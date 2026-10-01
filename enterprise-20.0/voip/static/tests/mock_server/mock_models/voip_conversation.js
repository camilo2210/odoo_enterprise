import { models } from "@web/../tests/web_test_helpers";

export class VoipConversation extends models.ServerModel {
    _name = "voip.conversation";

    /**
     * Mirrors the server-side find-or-create: every leg of one PBX
     * conversation, whichever order they reach us in, resolves to one row.
     *
     * @param {string} conversationIdentifier
     * @returns {number|false}
     */
    _get_or_create(conversationIdentifier) {
        if (!conversationIdentifier) {
            return false;
        }
        const [id] = this.search([
            ["conversation_identifier", "=", conversationIdentifier],
        ]);
        return id ?? this.create({ conversation_identifier: conversationIdentifier });
    }
}
