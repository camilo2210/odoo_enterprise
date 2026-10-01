from collections import defaultdict

from odoo import models


class MarketingActivity(models.Model):
    _inherit = 'marketing.activity'

    def action_delete_step(self, step_type):
        if step_type == 'delay':
            self._delete_delay()
        elif step_type == 'trigger':
            self._delete_trigger()
        else:
            self._delete_marketing_activity()

    def _delete_delay(self):
        """
            Used to remove the delay node off the tree in the campaign flow view.
            To do that we set its interval_number to 0.
            If the impacted node will become empty, we remove it.
        """
        activities_to_keep = self.filtered(
            lambda activity: activity._has_activity_node() or activity._has_trigger_node())
        for activity in activities_to_keep:
            coordinates = dict(activity.view_coordinates or {})
            coordinates.pop('delay', None)
            activity.write({
                'interval_number': 0,
                'view_coordinates': coordinates,
            })
        (self - activities_to_keep)._unlink_activity()

    def _delete_trigger(self):
        """
            Used to remove the trigger node off the tree in the campaign flow view.
            To do that we set its trigger_type back to activity or begin, depending if the activity has a parent or not.
            If the impacted node will become empty, we remove it.
        """
        activities_to_keep = self.filtered(
            lambda activity: activity._has_delay_node() or activity._has_activity_node())
        for activity in activities_to_keep:
            coordinates = dict(activity.view_coordinates or {})
            coordinates.pop('trigger', None)
            activity.write({
                'trigger_type': 'activity' if activity.parent_id else 'begin',
                'triggering_activity_id': False,
                'wait_value_domain': False,
                'view_coordinates': coordinates,
            })
        (self - activities_to_keep)._unlink_activity()

    def _delete_marketing_activity(self):
        """
            Used to remove an activity off the tree in the campaign flow view.
            To do that, we set the activity_type to `structure` so that the activity disappears from the tree.
            But we still keep the information linked to their options, interval_number/interval_type, trigger_type, etc.
            If the impacted node will become empty, we remove it.
        """
        activities_to_keep = self.filtered(
            lambda activity: activity._has_delay_node() or activity._has_trigger_node())
        for activity in activities_to_keep:
            coordinates = dict(activity.view_coordinates or {})
            coordinates.pop('activity', None)
            activity_values = {'activity_type': 'structure'}
            if activity.activity_type == 'split':
                activity_values.update({
                    'trigger_type': 'activity' if activity.parent_id else 'begin',
                    'triggering_activity_id': False,
                    'split_domain': False,
                })
                if not activity.child_ids:
                    if activity._has_delay_node() and 'delay' in coordinates:
                        last_node_coordinates = coordinates['delay']
                    elif activity._has_trigger_node() and 'trigger' in coordinates:
                        last_node_coordinates = coordinates['trigger']
                    else:
                        last_node_coordinates = self.env['marketing.campaign']._get_last_visible_node_coordinates(activity.parent_id)
                    coordinates.pop('no_branch_flag', None)
                    coordinates.pop('yes_branch_flag', None)
                    coordinates.update({
                        'flag': {
                            'x': last_node_coordinates['x'] + 350,
                            'y': last_node_coordinates['y'],
                        },
                    })
            activity_values.update({
                'view_coordinates': coordinates,
            })
            activity.write(activity_values)
        (self - activities_to_keep)._unlink_activity()

    def _unlink_activity(self):
        """
            Used to delete a marketing activity. This method removes the nodes
            associated with the specified activities, unlinks the newly invalid
            root nodes (activity triggers), and updates the position flag of the
            new leaf nodes.
        """
        activities_to_unlink = self

        # Step 1: Removes activity triggers that end up as root activities when
        #         the given activities are deleted.

        # When deleting a root node, its children are promoted to root nodes.
        # Since activity interaction types (`mail_open`, etc.) are stored in the
        # `trigger_type` field, and root nodes must have a `trigger_type` of
        # `begin` or `collect_reply`, activity interactions can not be kept on
        # the new root nodes and should therefore be removed.

        for root_activity_to_unlink in self.filtered(lambda activity: not activity.parent_id):
            descendants = root_activity_to_unlink.child_ids
            while descendants:
                activity = descendants[-1]
                descendants = descendants - activity
                if not activity._has_delay_node() and not activity._has_activity_node():
                    activities_to_unlink |= activity
                    descendants = descendants + activity.child_ids
                else:
                    coordinates = activity.view_coordinates or {}
                    coordinates.pop('trigger', None)
                    activity.write({
                        'parent_id': False,
                        'trigger_type': root_activity_to_unlink.trigger_type,
                        'triggering_activity_id': False,
                        'wait_value_domain': False,
                        'view_coordinates': coordinates,
                    })

        # Step 2: Relocate the END flags when deleting a leaf activity

        # The position of the END flags is stored on the activities
        # (see `view_coordinates`). When deleting a leaf activity, a flag
        # position should be assigned to the new leaf activity to prevent
        # the flag from being misplaced.

        for activity_to_unlink in activities_to_unlink:
            campaign = activity_to_unlink.campaign_id
            if activity_to_unlink.parent_id:
                if activity_to_unlink.parent_id in activities_to_unlink:
                    continue
                # Update the flag position of the parent's yes/no branches:
                if activity_to_unlink.parent_id.activity_type == 'split' and not activity_to_unlink.child_ids:
                    split_node = activity_to_unlink.parent_id
                    remaining_children = split_node.child_ids.filtered(lambda activity:
                        activity not in activities_to_unlink
                        and activity.is_split_no == activity_to_unlink.is_split_no)
                    if not remaining_children:
                        if activity_to_unlink._has_trigger_node() and 'trigger' in activity_to_unlink.view_coordinates:
                            first_node_coordinates = activity_to_unlink.view_coordinates['trigger']
                        elif activity_to_unlink._has_delay_node() and 'delay' in activity_to_unlink.view_coordinates:
                            first_node_coordinates = activity_to_unlink.view_coordinates['delay']
                        elif activity_to_unlink._has_activity_node() and 'activity' in activity_to_unlink.view_coordinates:
                            first_node_coordinates = activity_to_unlink.view_coordinates['activity']
                        else:
                            first_node_coordinates = activity_to_unlink.view_coordinates.get('flag', {'x': 0, 'y': 0})
                        split_node_coordinates = dict(split_node.view_coordinates or {})
                        split_node_coordinates.update({
                            'no_branch_flag' if activity_to_unlink.is_split_no else 'yes_branch_flag': {
                                'x': first_node_coordinates['x'],
                                'y': first_node_coordinates['y'],
                            },
                        })
                        split_node.write({
                            'view_coordinates': split_node_coordinates,
                        })
                # Update the flag position of the parent node:
                elif not activity_to_unlink.child_ids:
                    parent_node = activity_to_unlink.parent_id
                    remaining_cousin_nodes = parent_node.child_ids - activities_to_unlink
                    if not remaining_cousin_nodes:
                        # When the parent marketing activity will become a leaf:
                        last_visible_node_coordinates = campaign._get_last_visible_node_coordinates(parent_node)
                        parent_node_coordinates = dict(parent_node.view_coordinates or {})
                        parent_node_coordinates.update({
                            'flag': {
                                'x': last_visible_node_coordinates['x'] + 350,
                                'y': last_visible_node_coordinates['y'],
                            },
                        })
                        parent_node.write({
                            'view_coordinates': parent_node_coordinates,
                        })
            elif not activity_to_unlink.child_ids:
                campaign_coordinates = dict(campaign.view_coordinates) if campaign.view_coordinates else defaultdict(lambda: {'x': 0, 'y': 0})
                if activity_to_unlink.trigger_type == 'collect_reply':
                    # Update the flag position of the reply trigger:
                    remaining_root_nodes_triggered_by_reply_trigger = campaign.marketing_activity_ids.filtered(lambda activity:
                        activity not in activities_to_unlink
                        and not activity.parent_id
                        and activity.trigger_type == 'collect_reply')
                    if not remaining_root_nodes_triggered_by_reply_trigger:
                        campaign_coordinates.update({
                            'reply_trigger_flag': {
                                'x': campaign_coordinates.get('reply_trigger', {'x': 0})['x'] + 350,
                                'y': campaign_coordinates.get('reply_trigger', {'y': 0})['y']
                            },
                        })
                        campaign.write({
                            'view_coordinates': campaign_coordinates
                        })
                else:
                    # Update the flag position of the main trigger:
                    remaining_root_nodes_triggered_by_main_trigger = campaign.marketing_activity_ids.filtered(lambda activity:
                        activity not in activities_to_unlink
                        and not activity.parent_id
                        and activity.trigger_type != 'collect_reply')
                    if not remaining_root_nodes_triggered_by_main_trigger:
                        campaign_coordinates.update({
                            'trigger_flag': {
                                'x': campaign_coordinates['trigger']['x'] + 350,
                                'y': campaign_coordinates['trigger']['y']
                            },
                        })
                        campaign.write({
                            'view_coordinates': campaign_coordinates
                        })

        # Step 3: Relink the activities to skip the activities to unlink

        # When an activity is deleted, its child activity would still reference
        # the deleted activity (see: `parent_id`). We therefore need to update
        # the child's `parent_id` to reference the first ancestor in the
        # hierarchy that is not being deleted.

        for activity_to_unlink in activities_to_unlink:
            activity = activity_to_unlink
            parent_activity = activity.parent_id

            while parent_activity and parent_activity in activities_to_unlink:
                activity = parent_activity
                parent_activity = activity.parent_id

            if parent_activity:
                activity_to_unlink.child_ids.write({
                    'parent_id': parent_activity.id,
                })
            else:
                activity_to_unlink.child_ids.write({
                    'parent_id': False,
                    'trigger_type': activity.trigger_type
                        if activity.trigger_type in ['begin', 'collect_reply'] else 'begin'
                })
        activities_to_unlink.unlink()

    def _has_delay_node(self):
        return bool(self.interval_number)

    def _has_trigger_node(self):
        return self.activity_type != 'split' and self.trigger_type not in ['activity', 'begin', 'collect_reply']

    def _has_activity_node(self):
        return self.activity_type != 'structure'
