from __future__ import annotations

import typing

from ast import literal_eval
from odoo import models
from odoo.exceptions import ValidationError

if typing.TYPE_CHECKING:
    from collections.abc import Iterator
    from odoo.addons.marketing_automation.models.marketing_activity import MarketingActivity


class MarketingCampaign(models.Model):
    _inherit = 'marketing.campaign'

    # ------------------------------------------------------------
    # Step Creation
    # ------------------------------------------------------------

    def _traverse_children_dfs(self, activity: MarketingActivity) -> Iterator[MarketingActivity]:
        """ Traverse the hierarchy using a DFS traversal order. """
        stack = [activity]
        while stack:
            current = stack.pop()
            yield current
            stack.extend(current.child_ids)

    def _prepare_marketing_activity_values(self, step_type, values):
        if step_type in ['create_activity', 'update_record']:
            return {
                **values,
                'campaign_id': self.id,
                'activity_type': 'action',
            }
        return {
            **values,
            'campaign_id': self.id,
            'activity_type': 'structure' if step_type in ['delay', 'trigger'] else step_type,
        }

    def add_step_after(self, step_type, values, marketing_activity_id):
        """ Adds a step right after the given marketing activity (see: `marketing_activity_id`)

        :param step_type: Name of the activity to create
        :param values: Form values
        :param marketing_activity_id: Inserts the new marketing activity after that node
        """
        self.ensure_one()
        if not marketing_activity_id:
            return self._create_then_add_step_after(step_type, values)
        marketing_activity = self.env['marketing.activity'].browse(marketing_activity_id)

        # Order: Trigger > Delay > Activity
        if (
            step_type == 'delay'
            and not marketing_activity._has_delay_node()
            and not marketing_activity._has_activity_node()):

            previous_node_coordinates = self._get_previous_node_coordinates(marketing_activity, 'delay')
            marketing_activity_coordinates = dict(marketing_activity.view_coordinates or {})
            marketing_activity_coordinates.update({
                'delay': {
                    'x': previous_node_coordinates['x'] + 350,
                    'y': previous_node_coordinates['y'],
                },
                'flag': {
                    'x': previous_node_coordinates['x'] + 700,
                    'y': previous_node_coordinates['y'],
                },
            })
            marketing_activity.write({
                'interval_number': values.get('interval_number', 0),
                'interval_type': values.get('interval_type', 'hours'),
                'view_coordinates': marketing_activity_coordinates,
            })
            return marketing_activity

        # Insert the node after the given marketing activity:
        values_for_new_marketing_activity = {
            **self._prepare_marketing_activity_values(step_type, values),
            'parent_id': marketing_activity.id,
        }
        if values_for_new_marketing_activity.get('trigger_type', 'begin') in ['begin', 'collect_reply'] and values_for_new_marketing_activity.get('parent_id'):
            values_for_new_marketing_activity.update({
                'trigger_type': 'activity',
            })
        new_marketing_activity = self.env['marketing.activity'].create(values_for_new_marketing_activity)

        # Position the new node:
        new_node_coordinates_key = step_type if step_type in ['delay', 'trigger'] else 'activity'
        if new_marketing_activity.parent_id.activity_type == 'split':
            # Position the node at the branch flag position:
            branch_flag_coordinates = new_marketing_activity.parent_id.view_coordinates[
                'no_branch_flag' if new_marketing_activity.is_split_no else 'yes_branch_flag'] if new_marketing_activity.parent_id.view_coordinates else {'x': 0, 'y': 0}
            new_marketing_activity_coordinates = {
                new_node_coordinates_key: {
                    'x': branch_flag_coordinates['x'],
                    'y': branch_flag_coordinates['y'],
                },
            }
        else:
            # Position the node relatively to its parent node:
            previous_node_coordinates = self._get_previous_node_coordinates(new_marketing_activity, step_type)
            new_marketing_activity_coordinates = {
                new_node_coordinates_key: {
                    'x': previous_node_coordinates['x'] + 350,
                    'y': previous_node_coordinates['y'],
                },
            }

        if new_marketing_activity.activity_type == 'split':
            # Position the yes/no branches:
            new_marketing_activity_coordinates.update({
                'yes_branch_flag': {
                    'x': new_marketing_activity_coordinates[new_node_coordinates_key]['x'] + 350,
                    'y': new_marketing_activity_coordinates[new_node_coordinates_key]['y'] - 112.5,
                },
                'no_branch_flag': {
                    'x': new_marketing_activity_coordinates[new_node_coordinates_key]['x'] + 350,
                    'y': new_marketing_activity_coordinates[new_node_coordinates_key]['y'] + 112.5,
                },
            })
        else:
            # Position the END flag:
            new_marketing_activity_coordinates.update({
                'flag': {
                    'x': new_marketing_activity_coordinates[new_node_coordinates_key]['x'] + 350,
                    'y': new_marketing_activity_coordinates[new_node_coordinates_key]['y'],
                },
            })

        new_marketing_activity.write({
            'view_coordinates': new_marketing_activity_coordinates,
        })
        marketing_activity_coordinates = dict(marketing_activity.view_coordinates or {})
        if 'flag' in marketing_activity_coordinates:
            marketing_activity_coordinates.pop('flag')
            marketing_activity.write({
                'view_coordinates': marketing_activity_coordinates
            })

        return new_marketing_activity

    def _create_then_add_step_after(self, step_type, values):
        self.ensure_one()
        new_marketing_activity = self.env['marketing.activity'].create(
            self._prepare_marketing_activity_values(step_type, values))
        campaign_coordinates = dict(self.view_coordinates or {})

        # Set a coordinate for the reply trigger (if needed):
        if new_marketing_activity.trigger_type == 'collect_reply' and 'reply_trigger' not in campaign_coordinates:
            campaign_coordinates.update({
                'reply_trigger': {
                    'x': campaign_coordinates.get('trigger', {}).get('x', 0),
                    'y': campaign_coordinates.get('trigger', {}).get('y', 0) + 150,
                },
            })
            self.write({
                'view_coordinates': campaign_coordinates,
            })

        # Position the new node relatively to the right campaign trigger:
        new_node_coordinates_key = step_type if step_type in ['delay', 'trigger'] else 'activity'
        if new_marketing_activity.trigger_type == 'collect_reply':
            new_marketing_activity_coordinates = {
                new_node_coordinates_key: {
                    'x': campaign_coordinates.get('reply_trigger', {}).get('x', 0) + 350,
                    'y': campaign_coordinates.get('reply_trigger', {}).get('y', 0),
                },
            }
        else:
            new_marketing_activity_coordinates = {
                new_node_coordinates_key: {
                    'x': campaign_coordinates.get('trigger', {}).get('x', 0) + 350,
                    'y': campaign_coordinates.get('trigger', {}).get('y', 0),
                },
            }

        # Position the new activity flags relatively to the node itself:
        if new_marketing_activity.activity_type == 'split':
            # Position the yes/no branch flags for the split node:
            new_marketing_activity_coordinates.update({
                'yes_branch_flag': {
                    'x': new_marketing_activity_coordinates[new_node_coordinates_key]['x'] + 350,
                    'y': new_marketing_activity_coordinates[new_node_coordinates_key]['y'] - 112.5,
                },
                'no_branch_flag': {
                    'x': new_marketing_activity_coordinates[new_node_coordinates_key]['x'] + 350,
                    'y': new_marketing_activity_coordinates[new_node_coordinates_key]['y'] + 112.5,
                },
            })
        else:
            # Position the end flag for the other activities:
            new_marketing_activity_coordinates.update({
                'flag': {
                    'x': new_marketing_activity_coordinates[new_node_coordinates_key]['x'] + 350,
                    'y': new_marketing_activity_coordinates[new_node_coordinates_key]['y'],
                },
            })

        new_marketing_activity.write({
            'view_coordinates': new_marketing_activity_coordinates,
        })
        return new_marketing_activity

    def add_step_before(self, step_type, values, marketing_activity_id, after_fake_step_type):
        """ Adds a step right before the given marketing activity (marketing_activity_id) after the given fake step type
        :param step_type: Step type (i.e: log_note, email, action, ...)
        :param values: Form values
        :param marketing_activity_id: Inserts the new marketing activity before that node
        :param after_fake_step_type: Inserts the new markerting activity after the fake step type (i.e: 'trigger' or 'delay')
        """
        self.ensure_one()

        next_marketing_activity = self.env['marketing.activity'].search([('id', '=', marketing_activity_id)])
        if not next_marketing_activity:
            # Insert a new node after the main or reply trigger:
            return self._create_then_add_step_after(step_type, values)

        # Insert the "trigger" in the existing record (if possible):
        if (
            step_type == 'trigger'
            and next_marketing_activity.parent_id
            and next_marketing_activity.activity_type != 'split'
            and not next_marketing_activity._has_trigger_node()
            and after_fake_step_type is None):

            next_marketing_activity_coordinates = dict(next_marketing_activity.view_coordinates or {})
            if next_marketing_activity.parent_id.activity_type == 'split':
                next_node_coordinates = self._get_next_node_coordinates(next_marketing_activity, 'trigger')
                next_marketing_activity_coordinates.update({
                    'trigger': {
                        'x': next_node_coordinates['x'],
                        'y': next_node_coordinates['y'],
                    },
                })
            else:
                previous_node_coordinates = self._get_previous_node_coordinates(next_marketing_activity, 'trigger')
                next_marketing_activity_coordinates.update({
                    'trigger': {
                        'x': previous_node_coordinates['x'] + 350,
                        'y': previous_node_coordinates['y'],
                    },
                })
            self._translate_nodes(next_marketing_activity_coordinates, 'trigger', 350, 0)

            next_marketing_activity.write({
                'trigger_type': values.get('trigger_type', False),
                'triggering_activity_id': values.get('triggering_activity_id', False),
                'validity_duration': values.get('validity_duration', False),
                'validity_duration_number': values.get('validity_duration_number', 0),
                'validity_duration_type': values.get('validity_duration_type', 'hours'),
                'split_domain': values.get('split_domain', False),
                'wait_value_domain': values.get('wait_value_domain') or '[]',
                'view_coordinates': next_marketing_activity_coordinates,
            })

            # Shift all the child nodes to the right:
            marketing_activity_iterator = self._traverse_children_dfs(next_marketing_activity)
            next(marketing_activity_iterator)  # skip

            for child_marketing_activity in marketing_activity_iterator:
                child_marketing_activity_coordinates = dict(child_marketing_activity.view_coordinates or {})
                self._translate_nodes(child_marketing_activity_coordinates, False, 350, 0)
                child_marketing_activity.write({
                    'view_coordinates': child_marketing_activity_coordinates
                })
            return next_marketing_activity

        # Insert the "delay" in the existing record (if possible):
        if (
            step_type == 'delay'
            and not next_marketing_activity._has_delay_node()
            and (after_fake_step_type == 'trigger' or (after_fake_step_type is None and not next_marketing_activity._has_trigger_node()))):

            next_marketing_activity_coordinates = dict(next_marketing_activity.view_coordinates or {})
            if next_marketing_activity.parent_id.activity_type == 'split':
                next_node_coordinates = self._get_next_node_coordinates(next_marketing_activity, 'delay')
                next_marketing_activity_coordinates.update({
                    'delay': {
                        'x': next_node_coordinates['x'],
                        'y': next_node_coordinates['y'],
                    },
                })
            else:
                previous_node_coordinates = self._get_previous_node_coordinates(next_marketing_activity, 'delay')
                next_marketing_activity_coordinates.update({
                    'delay': {
                        'x': previous_node_coordinates['x'] + 350,
                        'y': previous_node_coordinates['y'],
                    },
                })
            self._translate_nodes(next_marketing_activity_coordinates, 'delay', 350, 0)

            next_marketing_activity.write({
                'interval_number': values.get('interval_number', 0),
                'interval_type': values.get('interval_type', 'hours'),
                'view_coordinates': next_marketing_activity_coordinates,
            })

            # Shift all the child nodes to the right:
            marketing_activity_iterator = self._traverse_children_dfs(next_marketing_activity)
            next(marketing_activity_iterator)  # skip

            for child_marketing_activity in marketing_activity_iterator:
                child_marketing_activity_coordinates = dict(child_marketing_activity.view_coordinates or {})
                self._translate_nodes(child_marketing_activity_coordinates, False, 350, 0)
                child_marketing_activity.write({
                    'view_coordinates': child_marketing_activity_coordinates
                })
            return next_marketing_activity

        if not next_marketing_activity.parent_id and step_type in ['split', 'trigger']:
            if next_marketing_activity._has_delay_node() and after_fake_step_type == 'delay':
                # Move the delay node to enable the insertion of the split/trigger node:
                new_marketing_activity_coordinates = {}
                next_marketing_activity_coordinates = dict(next_marketing_activity.view_coordinates or {})
                if 'delay' in next_marketing_activity_coordinates:
                    new_marketing_activity_coordinates.update({
                        'delay': next_marketing_activity_coordinates.pop('delay'),
                    })
                else:
                    campaign_trigger_node_coordinates = self._get_reply_trigger_coordinates() \
                        if next_marketing_activity.trigger_type == 'collect_reply' else self._get_trigger_coordinates()
                    new_marketing_activity_coordinates.update({
                        'delay': {
                            'x': campaign_trigger_node_coordinates['x'] + 300,
                            'y': campaign_trigger_node_coordinates['y'],
                        },
                    })
                new_marketing_activity = self.env['marketing.activity'].create({
                    'campaign_id': self.id,
                    'activity_type': 'structure',
                    'trigger_type': 'collect_reply' if next_marketing_activity.trigger_type == 'collect_reply' else 'begin',
                    'interval_number': next_marketing_activity.interval_number,
                    'interval_type': next_marketing_activity.interval_type,
                    'view_coordinates': new_marketing_activity_coordinates
                })
                next_marketing_activity_values = {
                    'interval_number': 0,
                    'interval_type': 'hours',
                    'view_coordinates': next_marketing_activity_coordinates,
                    'parent_id': new_marketing_activity.id,
                }
                if next_marketing_activity.trigger_type in ['begin', 'collect_reply']:
                    next_marketing_activity_values.update({
                        'trigger_type': 'activity',
                    })
                next_marketing_activity.write(next_marketing_activity_values)
                return self.add_step_before(step_type, values, marketing_activity_id, None)
            if step_type == 'split':
                raise ValidationError(self.env._("Cannot insert a if/else split as a root activity."))
            if step_type == 'trigger':
                raise ValidationError(self.env._("Cannot insert a condition delay as a root activity."))

        new_node_coordinates_key = step_type if step_type in ['delay', 'trigger'] else 'activity'

        # Insert the new node before the given node (and all its fake nodes):
        if after_fake_step_type not in ['delay', 'trigger']:
            if next_marketing_activity.parent_id.activity_type == 'split':
                child_node_coordinates = self._get_first_visible_node_coordinates(next_marketing_activity)
                new_marketing_activity_coordinates = {
                    new_node_coordinates_key: {
                        'x': child_node_coordinates['x'],
                        'y': child_node_coordinates['y'],
                    },
                }
            else:
                previous_node_coordinates = self._get_previous_node_coordinates(next_marketing_activity, False)
                new_marketing_activity_coordinates = {
                    new_node_coordinates_key: {
                        'x': previous_node_coordinates['x'] + 350,
                        'y': previous_node_coordinates['y'],
                    },
                }
            if step_type == 'split':
                new_marketing_activity_coordinates.update({
                    'yes_branch_flag': {
                        'x': new_marketing_activity_coordinates[new_node_coordinates_key]['x'] + 350,
                        'y': new_marketing_activity_coordinates[new_node_coordinates_key]['y'] - 112.5,
                    },
                    'no_branch_flag': {
                        'x': new_marketing_activity_coordinates[new_node_coordinates_key]['x'] + 350,
                        'y': new_marketing_activity_coordinates[new_node_coordinates_key]['y'] + 112.5,
                    },
                })

            # Create the new marketing activity with the given values:
            values_for_new_marketing_activity = {
                **self._prepare_marketing_activity_values(step_type, values),
                'parent_id': next_marketing_activity.parent_id.id,
                'is_split_no': next_marketing_activity.is_split_no,
                'view_coordinates': new_marketing_activity_coordinates,
            }
            if values_for_new_marketing_activity.get('trigger_type', 'begin') in ['begin', 'collect_reply'] and values_for_new_marketing_activity.get('parent_id'):
                values_for_new_marketing_activity.update({
                    'trigger_type': 'activity',
                })
            new_marketing_activity = self.env['marketing.activity'].create(values_for_new_marketing_activity)

            # Link the next marketing activity to the new one:
            values_for_next_marketing_activity = {
                'parent_id': new_marketing_activity.id,
                'is_split_no': False,
            }
            if next_marketing_activity.trigger_type in ['begin', 'collect_reply'] and values_for_next_marketing_activity.get('parent_id'):
                values_for_next_marketing_activity.update({
                    'trigger_type': 'activity',
                })
            next_marketing_activity.write(values_for_next_marketing_activity)

            # Shift all the child nodes to the right:
            marketing_activity_iterator = self._traverse_children_dfs(next_marketing_activity)
            for child_marketing_activity in marketing_activity_iterator:
                child_marketing_activity_coordinates = dict(child_marketing_activity.view_coordinates or {})
                self._translate_nodes(child_marketing_activity_coordinates, False, 350, 0)
                child_marketing_activity.write({
                    'view_coordinates': child_marketing_activity_coordinates,
                })
            return new_marketing_activity

        # Split the node:
        values_for_next_marketing_activity = {
            'is_split_no': False,
        }
        values_for_new_marketing_activity = {
            'is_split_no': next_marketing_activity.is_split_no,
        }

        new_marketing_activity_coordinates = {}
        next_marketing_activity_coordinates = dict(next_marketing_activity.view_coordinates or {})

        # Copy the delay values to the new marketing activity (if needed):
        if after_fake_step_type == 'delay':
            values_for_new_marketing_activity.update({
                'interval_number': next_marketing_activity.interval_number,
                'interval_type': next_marketing_activity.interval_type,
            })
            if step_type == 'delay':
                values_for_next_marketing_activity.update({
                    'interval_number': values.get('interval_number', False),
                    'interval_type': values.get('interval_type', False),
                })
            else:
                values_for_next_marketing_activity.update({
                    'interval_number': 0,
                    'interval_type': 'hours',
                })
            # Copy the delay node coordinates to the new nodes:
            if 'delay' in next_marketing_activity_coordinates:
                delay_node_coordinates = next_marketing_activity_coordinates.pop('delay')
                new_marketing_activity_coordinates.update({
                    'delay': delay_node_coordinates,
                })

        # Copy the trigger values to the new marketing activity (if needed):
        if next_marketing_activity.activity_type != 'split':
            values_for_new_marketing_activity.update({
                'trigger_type': next_marketing_activity.trigger_type,
                'triggering_activity_id': next_marketing_activity.triggering_activity_id.id,
                'validity_duration': next_marketing_activity.validity_duration,
                'validity_duration_number': next_marketing_activity.validity_duration_number,
                'validity_duration_type': next_marketing_activity.validity_duration_type,
                'wait_value_domain': next_marketing_activity.wait_value_domain,
            })
            if step_type == 'trigger':
                values_for_next_marketing_activity.update({
                    'trigger_type': values.get('trigger_type', 'activity'),
                    'triggering_activity_id': values.get('triggering_activity_id', False),
                    'validity_duration': values.get('validity_duration', False),
                    'validity_duration_number': values.get('validity_duration_number', 0),
                    'validity_duration_type': values.get('validity_duration_type', 'hours'),
                    'wait_value_domain': values.get('wait_value_domain') or '[]',
                })
            else:
                values_for_next_marketing_activity.update({
                    'trigger_type': 'activity',
                    'triggering_activity_id': False,
                    'validity_duration': False,
                    'validity_duration_number': 0,
                    'validity_duration_type': 'hours',
                    'wait_value_domain': False,
                })
            # Copy the trigger node coordinates:
            if 'trigger' in next_marketing_activity_coordinates:
                trigger_node_coordinates = next_marketing_activity_coordinates.pop('trigger')
                new_marketing_activity_coordinates.update({
                    'trigger': trigger_node_coordinates,
                })

        if 'delay' in new_marketing_activity_coordinates:
            last_node_coordinates = new_marketing_activity_coordinates['delay']
        elif 'trigger' in new_marketing_activity_coordinates:
            last_node_coordinates = new_marketing_activity_coordinates['trigger']
        else:
            last_node_coordinates = self._get_last_visible_node_coordinates(next_marketing_activity.parent_id)

        if step_type in ['delay', 'trigger']:
            values_for_new_marketing_activity = {
                'campaign_id': self.id,
                'activity_type': 'structure',
                **values_for_new_marketing_activity,
            }
            next_marketing_activity_coordinates.update({
                new_node_coordinates_key: last_node_coordinates,
            })
            self._translate_nodes(next_marketing_activity_coordinates, False, 350, 0)
        else:
            values_for_new_marketing_activity = {
                **self._prepare_marketing_activity_values(step_type, values),
                **values_for_new_marketing_activity,
            }
            new_marketing_activity_coordinates.update({
                new_node_coordinates_key: last_node_coordinates,
            })
            if step_type == 'split':
                new_marketing_activity_coordinates.update({
                    'yes_branch_flag': {
                        'x': new_marketing_activity_coordinates[new_node_coordinates_key]['x'] + 350,
                        'y': new_marketing_activity_coordinates[new_node_coordinates_key]['y'] - 112.5,
                    },
                    'no_branch_flag': {
                        'x': new_marketing_activity_coordinates[new_node_coordinates_key]['x'] + 350,
                        'y': new_marketing_activity_coordinates[new_node_coordinates_key]['y'] + 112.5,
                    },
                })
            self._translate_nodes(new_marketing_activity_coordinates, after_fake_step_type, 350, 0)
            self._translate_nodes(next_marketing_activity_coordinates, False, 350, 0)

        # Create the new node:
        values_for_new_marketing_activity.update({
            'parent_id': next_marketing_activity.parent_id.id,
            'view_coordinates': new_marketing_activity_coordinates,
        })
        if values_for_new_marketing_activity.get('parent_id'):
            values_for_new_marketing_activity.update({
                'trigger_type': 'activity',
            })
        new_marketing_activity = self.env['marketing.activity'].create(values_for_new_marketing_activity)

        # Update the existing node:
        values_for_next_marketing_activity.update({
            'parent_id': new_marketing_activity.id,
            'view_coordinates': next_marketing_activity_coordinates,
        })
        if values_for_next_marketing_activity.get('parent_id') and \
            values_for_new_marketing_activity.get('trigger_type', next_marketing_activity.trigger_type) in ['begin', 'collect_reply']:
            values_for_next_marketing_activity.update({
                'trigger_type': 'activity',
            })
        next_marketing_activity.write(values_for_next_marketing_activity)

        # Shift all the child nodes to the right:
        marketing_activity_iterator = self._traverse_children_dfs(next_marketing_activity)
        next(marketing_activity_iterator)  # skip
        for child_marketing_activity in marketing_activity_iterator:
            child_marketing_activity_coordinates = dict(child_marketing_activity.view_coordinates or {})
            self._translate_nodes(child_marketing_activity_coordinates, False, 350, 0)
            child_marketing_activity.write({
                'view_coordinates': child_marketing_activity_coordinates,
            })

        return new_marketing_activity

    def add_forking_step(self, step_type, values, marketing_activity_id, after_fake_step_type):
        marketing_activity = self.env['marketing.activity'].search([('id', '=', marketing_activity_id)])
        if not after_fake_step_type:
            return self.add_step_after(step_type, values, marketing_activity_id)
        elif after_fake_step_type == 'trigger':
            if marketing_activity._has_trigger_node():
                if marketing_activity._has_delay_node() or marketing_activity._has_activity_node():
                    # Split the node:
                    marketing_activity_coordinates = dict(marketing_activity.view_coordinates or {})
                    new_marketing_activity_coordinates = {}
                    if 'trigger' in marketing_activity_coordinates:
                        new_marketing_activity_coordinates.update({
                            'trigger': marketing_activity_coordinates.pop('trigger')
                        })
                    new_marketing_activity = self.env['marketing.activity'].create({
                        'campaign_id': self.id,
                        'activity_type': 'structure',
                        'parent_id': marketing_activity.parent_id.id,
                        'is_split_no': marketing_activity.is_split_no,
                        'view_coordinates': new_marketing_activity_coordinates,
                        # Trigger values:
                        'trigger_type': marketing_activity.trigger_type,
                        'triggering_activity_id': marketing_activity.triggering_activity_id.id,
                    })
                    marketing_activity.write({
                        'parent_id': new_marketing_activity.id,
                        'is_split_no': False,
                        'view_coordinates': marketing_activity_coordinates,
                        # Trigger values:
                        'trigger_type': 'activity',
                        'triggering_activity_id': False,
                    })
                    return self.add_step_after(step_type, values, new_marketing_activity.id)
                else:
                    return self.add_step_after(step_type, values, marketing_activity.id)
        elif after_fake_step_type == 'delay':
            if marketing_activity._has_delay_node():
                if marketing_activity._has_activity_node():
                    # Split the node:
                    marketing_activity_coordinates = dict(marketing_activity.view_coordinates or {})
                    new_marketing_activity_coordinates = {}
                    if 'trigger' in marketing_activity_coordinates:
                        new_marketing_activity_coordinates.update({
                            'trigger': marketing_activity_coordinates.pop('trigger')
                        })
                    if 'delay' in marketing_activity_coordinates:
                        new_marketing_activity_coordinates.update({
                            'delay': marketing_activity_coordinates.pop('delay')
                        })
                    new_marketing_activity = self.env['marketing.activity'].create({
                        'campaign_id': self.id,
                        'activity_type': 'structure',
                        'parent_id': marketing_activity.parent_id.id,
                        'is_split_no': marketing_activity.is_split_no,
                        'view_coordinates': new_marketing_activity_coordinates,
                        # Trigger values:
                        'trigger_type': marketing_activity.trigger_type,
                        'triggering_activity_id': marketing_activity.triggering_activity_id.id,
                        # Delay values:
                        'interval_number': marketing_activity.interval_number,
                        'interval_type': marketing_activity.interval_type,
                    })
                    marketing_activity.write({
                        'parent_id': new_marketing_activity.id,
                        'is_split_no': False,
                        'view_coordinates': marketing_activity_coordinates,
                        # Trigger values:
                        'trigger_type': 'activity',
                        'triggering_activity_id': False,
                        # Delay values:
                        'interval_number': 0,
                        'interval_type': 'hours',
                    })
                    return self.add_step_after(step_type, values, new_marketing_activity.id)
                else:
                    return self.add_step_after(step_type, values, marketing_activity.id)

    def _get_trigger_coordinates(self):
        campaign_coordinates = dict(self.view_coordinates or {})
        return {
            'x': campaign_coordinates.get('trigger', {}).get('x', 0),
            'y': campaign_coordinates.get('trigger', {}).get('y', 0),
        }

    def _get_reply_trigger_coordinates(self):
        campaign_coordinates = dict(self.view_coordinates or {})
        return {
            'x': campaign_coordinates.get('reply_trigger', {}).get('x', 0),
            'y': campaign_coordinates.get('reply_trigger', {}).get('y', 0),
        }

    def _get_first_visible_node_coordinates(self, marketing_activity):
        # Order: Trigger > Delay > Activity
        view_coordinates = marketing_activity.view_coordinates or {}
        if marketing_activity._has_trigger_node() and 'trigger' in view_coordinates:
            return view_coordinates['trigger']
        if marketing_activity._has_delay_node() and 'delay' in view_coordinates:
            return view_coordinates['delay']
        if marketing_activity._has_activity_node() and 'activity' in view_coordinates:
            return view_coordinates['activity']
        raise Exception('No node for the activity', marketing_activity)

    def _get_last_visible_node_coordinates(self, marketing_activity):
        # Order: Trigger > Delay > Activity
        while marketing_activity:
            view_coordinates = marketing_activity.view_coordinates or {}
            if marketing_activity._has_activity_node() and 'activity' in view_coordinates:
                return view_coordinates['activity']
            if marketing_activity._has_delay_node() and 'delay' in view_coordinates:
                return view_coordinates['delay']
            if marketing_activity._has_trigger_node() and 'trigger' in view_coordinates:
                return view_coordinates['trigger']
            if marketing_activity.parent_id:
                marketing_activity = marketing_activity.parent_id
            else:
                return self._get_reply_trigger_coordinates() \
                    if marketing_activity.trigger_type == 'collect_reply' \
                        else self._get_trigger_coordinates()
        return self._get_trigger_coordinates()

    def _get_next_node_coordinates(self, marketing_activity, step_type):
        # Order: Trigger > Delay > Activity
        view_coordinates = marketing_activity.view_coordinates or {}
        if step_type == 'trigger':
            if marketing_activity._has_delay_node() and 'delay' in view_coordinates:
                return view_coordinates['delay']
            if marketing_activity._has_activity_node() and 'activity' in view_coordinates:
                return view_coordinates['activity']
        if step_type == 'delay' and marketing_activity._has_activity_node() and 'activity' in view_coordinates:
            return view_coordinates['activity']

        return view_coordinates.get('flag', {'x': 0, 'y': 0})

    def _get_previous_node_coordinates(self, marketing_activity, step_type):
        # Order: Trigger > Delay > Activity
        if step_type:
            view_coordinates = marketing_activity.view_coordinates or {}
            if step_type == 'delay' and marketing_activity._has_trigger_node() and 'trigger' in view_coordinates:
                return view_coordinates['trigger']
            if step_type not in ['trigger', 'delay']:
                if marketing_activity._has_delay_node() and 'delay' in view_coordinates:
                    return view_coordinates['delay']
                if marketing_activity._has_trigger_node() and 'trigger' in view_coordinates:
                    return view_coordinates['trigger']

        parent_marketing_activity = marketing_activity.parent_id
        if not parent_marketing_activity:
            return self._get_reply_trigger_coordinates() \
                if marketing_activity.trigger_type == 'collect_reply' \
                    else self._get_trigger_coordinates()

        while parent_marketing_activity:
            view_coordinates = parent_marketing_activity.view_coordinates or {}
            if parent_marketing_activity._has_activity_node() and 'activity' in view_coordinates:
                return view_coordinates['activity']
            elif parent_marketing_activity._has_delay_node() and 'delay' in view_coordinates:
                return view_coordinates['delay']
            elif parent_marketing_activity._has_trigger_node() and 'trigger' in view_coordinates:
                return view_coordinates['trigger']
            parent_marketing_activity = parent_marketing_activity.parent_id

        return self._get_trigger_coordinates()

    def _translate_nodes(self, marketing_activity_coordinates, after_fake_step_type, dx=0, dy=0):
        """ Translates the nodes, its fake nodes (delay, trigger) and its flags. """
        if 'activity' in marketing_activity_coordinates:
            marketing_activity_coordinates.update({
                'activity': {
                    'x': marketing_activity_coordinates['activity']['x'] + dx,
                    'y': marketing_activity_coordinates['activity']['y'] + dy,
                },
            })

        if after_fake_step_type != 'delay':
            if 'delay' in marketing_activity_coordinates:
                marketing_activity_coordinates.update({
                    'delay': {
                        'x': marketing_activity_coordinates['delay']['x'] + dx,
                        'y': marketing_activity_coordinates['delay']['y'] + dy,
                    },
                })
            if after_fake_step_type != 'trigger':
                if 'trigger' in marketing_activity_coordinates:
                    marketing_activity_coordinates.update({
                        'trigger': {
                            'x': marketing_activity_coordinates['trigger']['x'] + dx,
                            'y': marketing_activity_coordinates['trigger']['y'] + dy,
                        },
                    })

        if 'flag' in marketing_activity_coordinates:
            marketing_activity_coordinates.update({
                'flag': {
                    'x': marketing_activity_coordinates['flag']['x'] + dx,
                    'y': marketing_activity_coordinates['flag']['y'] + dy,
                },
            })
        if 'yes_branch_flag' in marketing_activity_coordinates:
            marketing_activity_coordinates.update({
                'yes_branch_flag': {
                    'x': marketing_activity_coordinates['yes_branch_flag']['x'] + dx,
                    'y': marketing_activity_coordinates['yes_branch_flag']['y'] + dy,
                },
            })
        if 'no_branch_flag' in marketing_activity_coordinates:
            marketing_activity_coordinates.update({
                'no_branch_flag': {
                    'x': marketing_activity_coordinates['no_branch_flag']['x'] + dx,
                    'y': marketing_activity_coordinates['no_branch_flag']['y'] + dy,
                },
            })

        return marketing_activity_coordinates

    def action_create_step(self, step_type):
        """ Returns the action to use to create a new step. """
        self.ensure_one()
        if step_type == 'log_note':
            action = self.env['ir.actions.act_window']._for_xml_id(
                'marketing_automation.marketing_activity_open_log_note_form_view')
            action['context'] = {
                **literal_eval(action['context'] or '{}'),
                'default_campaign_id': self.id,
            }
            return action
        if step_type in ['mail', 'action', 'split']:
            action = self.env['ir.actions.act_window']._for_xml_id(
                'marketing_automation.marketing_activity_open_marketing_activity_form_view')
            action['context'] = {
                **literal_eval(action['context'] or '{}'),
                'default_activity_type': step_type,
                'default_campaign_id': self.id,
            }
            return action
        if step_type == 'delay':
            action = self.env['ir.actions.act_window']._for_xml_id(
                'marketing_automation.marketing_activity_open_delay_form_view')
            action['context'] = {
                **literal_eval(action['context'] or '{}'),
                'default_campaign_id': self.id,
                'default_interval_number': 1,
            }
            return action
        if step_type == 'trigger':
            action = self.env['ir.actions.act_window']._for_xml_id(
                'marketing_automation.marketing_activity_open_trigger_form_view')
            action['context'] = {
                **literal_eval(action['context'] or '{}'),
                'default_campaign_id': self.id,
                'default_model_id': self.model_id.id,
            }
            return action
        if step_type == 'subscribe_to_list':
            action = self.env['ir.actions.act_window']._for_xml_id(
                'marketing_automation.marketing_activity_open_subscribe_to_list_form_view')
            action['context'] = {
                **literal_eval(action['context'] or '{}'),
                'default_campaign_id': self.id,
                'default_model_id': self.model_id.id,
            }
            return action
        if step_type == 'create_activity':
            action = self.env['ir.actions.act_window']._for_xml_id(
                'marketing_automation.marketing_activity_action_open_ir_actions_server_form_view')
            action['context'] = {
                **literal_eval(action['context'] or '{}'),
                'is_modal': True,
                'default_model_id': self.model_id.id,
                'default_state': 'next_activity',
            }
            return action
        if step_type == 'update_record':
            action = self.env['ir.actions.act_window']._for_xml_id(
                'marketing_automation.marketing_activity_action_open_ir_actions_server_form_view')
            action['context'] = {
                **literal_eval(action['context'] or '{}'),
                'is_modal': True,
                'default_model_id': self.model_id.id,
                'default_state': 'object_write',
            }
            return action
        raise Exception(f'Unknown step type: {step_type}')

    def action_edit_step(self, step_type, marketing_activity_id):
        """ Returns the action to use to edit the step. """
        if step_type == 'action':
            marketing_activity = self.env['marketing.activity'].browse(marketing_activity_id)
            if marketing_activity:
                if marketing_activity.server_action_state == 'object_write':
                    # Model: ir.actions.server
                    action = self.action_create_step('update_record')
                    action['res_id'] = marketing_activity.server_action_id.id
                    action['context'].update({
                        'active_marketing_activity_id': marketing_activity_id
                    })
                    return action
                elif marketing_activity.server_action_state == 'next_activity':
                    # Model: ir.actions.server
                    action = self.action_create_step('create_activity')
                    action['res_id'] = marketing_activity.server_action_id.id
                    action['context'].update({
                        'active_marketing_activity_id': marketing_activity_id
                    })
                    return action
                else:
                    # Model: marketing.activity
                    action = self.action_create_step('action')
                    action['res_id'] = marketing_activity_id
                    return action
        # Model: marketing.activity
        action = self.action_create_step(step_type)
        action['res_id'] = marketing_activity_id
        return action

    def action_sort_steps(self):
        for campaign in self:

            row_height = {}

            def computed_row_height(activity):
                for child in activity.child_ids:
                    computed_row_height(child)
                row_height[activity.id] = 150
                if activity.activity_type == 'split':
                    no_branch_children = activity.child_ids.filtered('is_split_no')
                    yes_branch_children = activity.child_ids - no_branch_children
                    # Allocate space for the missing "yes" branch:
                    if not yes_branch_children:
                        row_height[activity.id] += 150
                    # Allocate space for the missing "no" branch:
                    if not no_branch_children:
                        row_height[activity.id] += 150
                    for child in activity.child_ids:
                        row_height[activity.id] += row_height.get(child.id, 0)
                elif len(activity.child_ids) == 1:
                    row_height[activity.id] = max(
                        row_height.get(activity.id, 0),
                        row_height.get(activity.child_ids.id, 0))
                elif len(activity.child_ids) > 1:
                    for child in activity.child_ids:
                        row_height[activity.id] += row_height.get(child.id, 0)

            def set_coordinates(activity, x, y):
                activity_coordinates = {}
                if activity._has_trigger_node():
                    activity_coordinates.update({
                        'trigger': {'x': x, 'y': y},
                    })
                    x += 350
                if activity._has_delay_node():
                    activity_coordinates.update({
                        'delay': {'x': x, 'y': y},
                    })
                    x += 350
                if activity._has_activity_node():
                    activity_coordinates.update({
                        'activity': {'x': x, 'y': y},
                    })
                    x += 350

                # Split node:
                if activity.activity_type == 'split':
                    no_branch_children = activity.child_ids.filtered('is_split_no')
                    yes_branch_children = activity.child_ids - no_branch_children

                    height = row_height.get(activity.id, 0)
                    n = len(activity.child_ids)
                    if not no_branch_children:
                        n += 1
                    if not yes_branch_children:
                        n += 1

                    k = 0
                    if not yes_branch_children:
                        activity_coordinates.update({
                            'yes_branch_flag': {
                                'x': x,
                                'y': y + (k / n) * height - height / 2 + (height / (2 * n)),
                            },
                        })
                        k += 1
                    for child in yes_branch_children:
                        set_coordinates(
                            child,
                            x,
                            y + (k / n) * height - height / 2 + (height / (2 * n)))
                        k += 1
                    if not no_branch_children:
                        activity_coordinates.update({
                            'no_branch_flag': {
                                'x': x,
                                'y': y + (k / n) * height - height / 2 + (height / (2 * n)),
                            },
                        })
                        k += 1
                    for child in no_branch_children:
                        set_coordinates(
                            child,
                            x,
                            y + (k / n) * height - height / 2 + (height / (2 * n)))
                else:
                    if activity.child_ids:
                        height = row_height.get(activity.id, 0)
                        n = len(activity.child_ids)
                        for k, child in enumerate(activity.child_ids):
                            set_coordinates(
                                child,
                                x,
                                y + (k / n) * height - height / 2 + (height / (2 * n)))
                    else:
                        activity_coordinates.update({
                            'flag': {'x': x, 'y': y},
                        })

                activity.write({
                    'view_coordinates': activity_coordinates,
                })

            root_activities = campaign.marketing_activity_ids.filtered(
                lambda activity: not activity.parent_id)
            root_activities_triggered_by_reply_trigger = root_activities.filtered(
                lambda activity: activity.trigger_type == 'collect_reply')
            root_activities_triggered_by_main_trigger = root_activities - root_activities_triggered_by_reply_trigger

            for root_activity in root_activities:
                computed_row_height(root_activity)

            total_row_height_for_main_trigger_nodes = 0
            for root_activity in root_activities_triggered_by_main_trigger:
                total_row_height_for_main_trigger_nodes += row_height.get(root_activity.id, 0)
            total_row_height_for_main_trigger_nodes = max(
                total_row_height_for_main_trigger_nodes, 150)

            n = len(root_activities_triggered_by_main_trigger)
            for k, root_activity in enumerate(root_activities_triggered_by_main_trigger):
                h = total_row_height_for_main_trigger_nodes
                set_coordinates(
                    root_activity,
                    350,
                    (k / n) * h - h / 2 + (h / (2 * n)))

            campaign_coordinates = {
                'trigger': {'x': 0, 'y': 0},
            }
            if not root_activities_triggered_by_main_trigger:
                campaign_coordinates.update({
                    'trigger_flag': {'x': 350, 'y': 0},
                })

            if campaign.marketing_activity_ids.filtered_domain([('trigger_type', '=', 'collect_reply')]):
                total_row_height_for_reply_trigger_nodes = 0
                for root_activity in root_activities_triggered_by_reply_trigger:
                    total_row_height_for_reply_trigger_nodes += row_height.get(root_activity.id, 0)
                total_row_height_for_reply_trigger_nodes = max(
                    total_row_height_for_reply_trigger_nodes, 150)

                y = (total_row_height_for_main_trigger_nodes + total_row_height_for_reply_trigger_nodes) / 2
                campaign_coordinates.update({
                    'reply_trigger': {'x': 0, 'y': y},
                })

                n = len(root_activities_triggered_by_reply_trigger)
                h = total_row_height_for_reply_trigger_nodes
                for k, root_activity in enumerate(root_activities_triggered_by_reply_trigger):
                    set_coordinates(
                        root_activity,
                        350,
                        y + (k / n) * h - h / 2 + (h / (2 * n)))

                if not root_activities_triggered_by_reply_trigger:
                    campaign_coordinates.update({
                        'reply_trigger_flag': {'x': 350, 'y': y},
                    })

            campaign.write({
                'view_coordinates': campaign_coordinates,
            })
