<?xml version="1.0" encoding="UTF-8"?>
<templates>
    <t t-name="knowledge.OptionsDropdown">
        <Dropdown beforeOpen.bind="this.beforeOpen" navigationOptions="{ 'shouldFocusChildInput': false }" menuClass="'o_knowledge_options_dropdown'" position="'bottom-end'">
            <button class="btn btn-light" data-hotkey="p" title="More actions">
                <i class="oi" data-icon="more_vert"/>
            </button>
            <t t-set-slot="content">
                <t t-if="this.props.record.data.active">
                    <t t-if="this.props.record.data.user_can_write">
                        <t t-if="!this.props.record.data.is_locked">
                            <DropdownItem t-if="this.props.record.data.icon" onSelected.bind="this.removeIcon">
                                <i class="oi oi-fw me-2" data-icon="cancel"/>Remove Icon
                            </DropdownItem>
                            <DropdownItem t-else="" onSelected.bind="this.addIcon">
                                <i class="oi oi-fw me-2" data-icon="add_reaction"/>Add Icon
                            </DropdownItem>
                            <t t-if="this.isInternalUser">
                                <DropdownItem t-if="this.props.record.data.cover_image_id" onSelected.bind="this.removeCover">
                                    <i class="oi oi-fw me-2" data-icon="close"/>Remove Cover
                                </DropdownItem>
                                <DropdownItem t-else="" onSelected.bind="this.addCover">
                                    <i class="oi oi-fw me-2" data-icon="image"/>Add Cover
                                </DropdownItem>
                                <t t-set="title">Properties are fields that can only be added on articles that have a parent.</t>
                                <DropdownItem t-if="!this.props.record.data.parent_id and this.isInternalUser" class="'text-muted o_disabled_option'" onSelected="() => {}" attrs="{title}" closingMode="'none'">
                                    <i class="oi oi-fw me-2" data-icon="settings_applications"/>Add Properties
                                </DropdownItem>
                                <DropdownItem t-elif="!this.props.record.data.article_properties.some((prop) => !prop.definition_deleted) and !this.panelState.isDisplayed('properties') and this.isInternalUser" onSelected.bind="() => this.panelState.setActivePanel('properties')">
                                    <i class="oi oi-fw me-2" data-icon="settings_applications"/>Add Properties
                                </DropdownItem>
                            </t>
                        </t>
                        <CheckboxItem onSelected.bind="this.toggleFullWidth" checked="this.props.record.data.full_width" class="'d-inline-flex justify-content-between'" closingMode="'none'">
                            <div class="pe-3">
                                <i class="oi oi-fw me-2" data-icon="arrow_range"/>Full Width
                            </div>
                            <div class="form-check form-switch">
                                <input class="form-check-input" type="checkbox" t-att-checked="this.props.record.data.full_width" tabindex="-1" aria-hidden="true"/>
                            </div>
                        </CheckboxItem>
                        <hr class="dropdown-divider"/>
                    </t>
                    <DropdownItem t-if="this.isInternalUser and this.props.record.data.user_can_write and !this.props.record.data.is_article_item" onSelected.bind="this.moveArticle" attrs="{'name': 'move_to'}">
                        <i class="oi oi-fw me-2" data-icon="keyboard_double_arrow_right"/>Move To
                    </DropdownItem>
                    <CheckboxItem t-if="this.props.record.data.user_can_write" onSelected.bind="this.toggleLock" checked="this.props.record.data.is_locked" closingMode="'none'" class="'d-inline-flex justify-content-between'">
                        <t t-if="this.props.record.data.is_locked">
                            <div class="pe-3">
                                <i class="oi oi-fw me-2" data-icon="lock_open"/>Unlock
                            </div>
                            <div class="form-check form-switch">
                                <input class="form-check-input" type="checkbox" t-att-checked="this.props.record.data.is_locked" tabindex="-1" aria-hidden="true"/>
                            </div>
                        </t>
                        <t t-else="">
                            <div class="pe-3">
                                <i class="oi oi-fw me-2" data-icon="lock"/>Lock Content
                            </div>
                            <div class="form-check form-switch">
                                <input class="form-check-input" type="checkbox" t-att-checked="this.props.record.data.is_locked" tabindex="-1" aria-hidden="true"/>
                            </div>
                        </t>
                    </CheckboxItem>
                    <DropdownItem t-if="this.canCreateArticle" onSelected.bind="this.copy">
                        <i class="oi oi-fw me-2" data-icon="content_copy"/>Create a Copy
                    </DropdownItem>
                    <DropdownItem t-if="this.isInternalUser and this.props.record.data.user_can_write and !this.creationDate.equals(this.lastEditionDate)" onSelected.bind="this.openHistory">
                        <i class="oi oi-fw me-2" data-icon="history"/>Open Version History
                    </DropdownItem>
                    <DropdownItem t-if="!this.props.record.data.is_article_item and this.props.record.data.user_can_write and this.props.record.data.parent_id" onSelected.bind="this.toggleItem">
                        <i class="oi oi-fw me-2" data-icon="checklist"/>Convert into Article Item
                    </DropdownItem>
                    <DropdownItem t-elif="this.props.record.data.is_article_item and this.props.record.data.user_can_write and !this.data.has_item_parent" onSelected.bind="this.toggleItem">
                        <i class="oi oi-fw me-2" data-icon="account_tree"/>Convert into Article
                    </DropdownItem>
                    <DropdownItem onSelected.bind="this.export" attrs="{ 'name': 'export' }">
                        <i class="oi oi-fw me-2" data-icon="download"/>Download PDF
                    </DropdownItem>
                    <DropdownItem t-if="this.props.record.data.user_can_write and this.isInternalUser" onSelected.bind="this.toggleIsListedInTemplatesGallery">
                        <i class="oi oi-fw me-2" data-icon="brush"/>
                        <t t-if="this.data.is_listed_in_templates_gallery">Remove from Templates</t>
                        <t t-else="">Add to Templates</t>
                    </DropdownItem>
                    <DropdownItem t-if="this.props.record.data.user_can_write and (this.isInternalUser or this.props.record.data.category === 'private')" onSelected.bind="this.sendToTrash" attrs="{'name': 'move_to_trash'}">
                        <i class="oi oi-fw oi-filled me-2" data-icon="delete"/>Move to Trash
                    </DropdownItem>
                </t>
                <t t-elif="this.props.record.data.user_can_write">
                    <t t-if="this.props.record.data.to_delete">
                        <DropdownItem t-if="this.isInternalUser or this.props.record.data.category === 'private'" onSelected.bind="this.unarchive">
                            <i class="oi oi-fw me-2" data-icon="delete"/>Restore from Trash
                        </DropdownItem>
                    </t>
                    <DropdownItem t-else="" onSelected.bind="this.unarchive">
                        <i class="oi oi-fw me-2" data-icon="archive"/>Unarchive
                    </DropdownItem>
                </t>
                <hr class="dropdown-divider"/>
                <div t-if="this.lastEditionDate" class="o_knowledge_options_dropdown_section px-2 text-muted small">
                    Last edited by <t t-out="this.lastEditor"/>
                    <div class="text-muted" t-att-title="this.formatDateTime(this.lastEditionDate)">
                        <t t-out="this.lastEditionDate.toRelative()"/>
                    </div>
                </div>
            </t>
        </Dropdown>
    </t>
</templates>
