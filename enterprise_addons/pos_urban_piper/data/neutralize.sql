-- disable urbanpiper
UPDATE pos_urbanpiper_store
SET urbanpiper_username = 'demo',
    urbanpiper_apikey = 'demo',
    is_webhook_register = False;
