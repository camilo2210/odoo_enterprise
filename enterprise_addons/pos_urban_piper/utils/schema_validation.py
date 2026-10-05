# Part of Odoo. See LICENSE file for full copyright and licensing details.

from ...pos_enterprise.models.data_validator import object_of, list_of

order_data_schema = object_of({
    'order': object_of({
        'items': list_of(object_of({
            'title': True,
            'price': True,
            'merchant_id': True,
            'quantity': True,
        })),
        'details': object_of({
            'order_subtotal': True,
            'total_taxes': True,
            'order_state': True,
            'channel': True,
            'id': True,
        }),
        'payment': True,
        'store': object_of({
            'merchant_ref_id': True,
        }),
    }),
    'customer': object_of({
        'name': True,
        'email': True,
        'phone': True,
        'address': True,
    }),
})

order_status_update_schema = object_of({
    'order_id': True,
    'new_state': True,
    'store_id': True,
})

rider_status_update_schema = object_of({
    'delivery_info': object_of({
        'current_state': True,
        'delivery_person_details': object_of({
            'name': True,
            'phone': True,
        }),
    }),
    'order_id': True,
    'store': object_of({
        'ref_id': True,
    }),
})

store_action_schema = object_of({
    'status': True,
    'platform': True,
    'action': True,
    'location_ref_id': True,
})

EVENT_TYPE_SCHEMAS = {
    'order_placed': order_data_schema,
    'order_status_update': order_status_update_schema,
    'rider_status_update': rider_status_update_schema,
    'store_action': store_action_schema,
}


def get_store_ref_id(data, event_type):
    if event_type == 'order_placed':
        return data['order']['store']['merchant_ref_id']
    if event_type == 'order_status_update':
        return data['store_id']
    if event_type == 'rider_status_update':
        return data['store']['ref_id']
    if event_type == 'store_action':
        return data['location_ref_id']
    return False


def validate_urbanpiper_schema(event_type, data):
    if event_type not in EVENT_TYPE_SCHEMAS:
        return True, ''
    return EVENT_TYPE_SCHEMAS[event_type](data)


# Status mapping for urbanpiper Webhooks
ORDER_STATUS_MAPPING = {
    'Placed': [1, 'placed'],
    'Acknowledged': [2, 'acknowledged'],
    'Food Ready': [3, 'food_ready'],
    'Dispatched': [4, 'dispatched'],
    'Completed': [5, 'completed'],
    'Cancelled': [6, 'cancelled'],
}

# Doc for UrbanPiper Webhook Event Types
# https://api-docs.urbanpiper.com/downstream/api/references/webhook-event-headers
URBANPIPER_WEBHOOK_EVENT_MAPPING = {
    '18': 'order_placed',
    '10005': 'user_feedback',
    '60008': 'order_status_update',
    '60012': 'rider_status_update',
    '60013': 'inventory_update',
    '60014': 'store_creation',
    '60015': 'store_action',
    '60016': 'catalogue_timing_grp',
    '60017': 'order_feature_update',
    '60018': 'order_items_oos_processed',
    '12002': 'hub_menu_publish',
    '12004': 'item_state_toggle',
    '12005': 'option_state_toggle',
}
