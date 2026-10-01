<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">
    <t t-name="knowledge.PermissionPanel">
        <div class="o_knowledge_permission_panel p-3 gap-2 overflow-y-auto">
            <div class="o_knowledge_restriction_message d-flex align-items-center py-1" t-if="this.data.is_desynchronized and this.state.isArticleLoaded">
                <i class="oi oi-fw oi-2x mx-1" data-icon="security"/>
                <div class="flex-grow-1 px-3">
                    Access Restricted. <t t-if="this.parentArticle.id">May not be shared with everyone from</t>
                    <a t-if="this.parentArticle.id" class="ps-1" href="#" t-on-click="() => this.openArticle(this.parentArticle.id)" t-out="this.parentArticle.name"/>
                </div>
                <button t-if="this.userIsInternalEditor" class="btn btn-link" t-on-click="this.restoreArticle">Restore</button>
            </div>
            <div class="o_internal_permission d-flex align-items-center gap-2 py-1" t-if="this.userIsInternal and this.state.isArticleLoaded">
                <div class="flex-grow-1 text-truncate">
                    <h5 class="mb-0">General Access</h5>
                    <div t-if="this.data.inherited_permission_parent_id" class="o_knowledge_internal_permission_based_on_text text-truncate text-muted">
                        Based on <a href="#" t-on-click="() => this.openArticle(this.inheritedPermissionParent.id)" t-out="this.inheritedPermissionParent.name"/>
                    </div>
                </div>
                <Dropdown menuClass="'d-flex flex-column min-w-0'">
                    <button class="o-dropdown-caret btn btn-outline-secondary"
                            t-att-class="{
                                'disabled': !this.userCanEdit,
                            }"
                            t-out="this.internalPermissions[this.data.inherited_permission]"
                    />
                    <t t-set-slot="content">
                        <t t-foreach="this.internalPermissions" t-as="permission" t-key="permission">
                            <DropdownItem onSelected="() => this.selectInternalPermission(permission)"
                                            class="{ 'flex-grow-1': true, active: permission === this.data.inherited_permission }"
                                            t-out="permission_value"
                            />
                        </t>
                    </t>
                </Dropdown>
            </div>
            <div t-if="this.userIsInternal and this.isRootArticle and this.data.inherited_permission !== 'none' and this.state.isArticleLoaded" class="o_internal_visibility d-flex align-items-center mt-1">
                <div class="flex-grow-1">Show in Workspace</div>
                <Dropdown menuClass="'d-flex flex-column min-w-0'">
                    <button class="o-dropdown-caret btn btn-outline-secondary"
                            t-att-class="{
                                'disabled': !this.userCanEdit,
                            }"
                            t-out="this.visibilities[this.visibility]"
                    />
                    <t t-set-slot="content">
                        <t t-foreach="this.visibilities" t-as="visibilityValue" t-key="visibilityValue">
                            <DropdownItem onSelected="() => this.selectInternalVisibility(visibilityValue)"
                                            class="{ 'flex-grow-1': true, active: visibilityValue === this.visibility }"
                                            t-out="visibilityValue_value"
                            />
                        </t>
                    </t>
                </Dropdown>
            </div>
            <hr class="mx-n3 my-3" t-if="this.userIsInternal and this.state.isArticleLoaded"/>
            <div class="d-flex align-items-center justify-content-between" t-if="this.userIsInternalEditor">
                <h5 class="mb-0">Members</h5>
                <button t-on-click="this.openInviteDialog" class="o_invite_selector btn btn-primary">
                    <i class="oi me-1" data-icon="add"/>
                    Share
                </button>
            </div>
            <div class="py-3 text-center" t-if="!this.state.isArticleLoaded">
                <i class="oi oi-2x oi-spin" data-icon="autorenew"/>
            </div>
            <div t-if="this.members and this.state.isArticleLoaded" class="o_knowledge_permission_panel_members mt-1">
                <div class="d-flex align-items-center py-1" t-foreach="this.members"
                        t-as="member" t-key="member.id">
                    <t t-set="isUniqueWriter" t-value="this.hasUniqueWriter and member.canWrite"/>
                    <t t-set="noRightsEscalation"
                        t-value="member.isCurrentUser and ((this.userIsInternal and this.permissionLevel[member.permission] gte this.permissionLevel[this.data.inherited_permission]) or this.userIsAdmin)"/>
                    <t t-set="canEditOtherMember"
                        t-value="!member.isCurrentUser and !isUniqueWriter and this.userIsInternalEditor"/>
                    <div>
                        <img t-if="this.userIsInternal and !member.partner_share" class="o_avatar rounded cursor-pointer"
                            t-att-src="member.avatarUrl"
                            t-on-click="() => this.onMemberClick(member)"/>
                        <img t-else="" class="o_avatar rounded" t-att-src="member.avatarUrl"/>
                    </div>
                    <div class="flex-grow-1 text-truncate px-2">
                        <div class="d-flex flex-row gap-1">
                            <div class="text-truncate" t-out="member.name"/>
                            <span t-if="member.isCurrentUser" class="text-muted">(You)</span>
                            <span t-elif="member.partner_share" class="text-muted">(Guest)</span>
                            <span t-if="member.isCurrentUser and this.userIsAdmin">
                                <i class="oi oi-filled pe-1" data-icon="settings"/>
                            </span>
                        </div>
                        <div class="text-muted text-truncate">
                            <span t-if="member.email" t-out="member.email" t-att-title="member.email"/>
                        </div>
                        <div t-if="member.based_on" class="text-muted text-truncate">
                            Based on
                            <a href="#" t-on-click="() => this.openArticle(member.based_on)">
                                <i t-if="!member.based_on_icon" class="oi text-muted me-1" data-icon="description"/>
                                <t t-out="member.basedOnName"/>
                            </a>
                        </div>
                    </div>
                    <div class="flex-shrink-0">
                        <Dropdown menuClass="'d-flex flex-column min-w-0'">
                            <button class="o-dropdown-caret btn btn-outline-secondary"
                                    t-att-class="{
                                        disabled: !noRightsEscalation and !canEditOtherMember,
                                    }" t-out="this.permissions[member.permission]"
                            />
                            <t t-set-slot="content">
                                <t t-if="!isUniqueWriter and this.userIsInternalEditor and this.data.category !== 'private'" t-foreach="this.permissions" t-as="permission" t-key="permission">
                                    <DropdownItem class="{'flex-grow-1': true, active: permission === member.permission}" onSelected="() => this.selectMemberPermission(member, permission)" t-out="permission_value"/>
                                </t>
                                <hr class="dropdown-divider"/>
                                <DropdownItem onSelected="() => this.removeMember(member)" class="'o_knowledge_permission_panel_remove_member flex-grow-1'">
                                    <t t-if="member.isCurrentUser">Leave</t>
                                    <t t-else="">Remove</t>
                                </DropdownItem>
                            </t>
                        </Dropdown>
                    </div>
                </div>
                <div t-if="this.userIsAdmin and this.data.user_permission !== 'write'" class="d-flex align-items-center py-1 my-1 text-muted">
                    <i class="d-flex align-items-center ps-2"><i class="oi oi-filled me-4 pe-1" data-icon="settings"/>As an administrator, you can always edit this article.</i>
                </div>
            </div>
        </div>
    </t>
</templates>
