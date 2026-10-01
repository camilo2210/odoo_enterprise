-- Delete VAPID public and private keys:
DELETE FROM ir_config_parameter WHERE key IN (
    'social_push_notifications.vapid_public_key',
    'social_push_notifications.vapid_private_key');
