-- neutralize Lazada API credentials
UPDATE lazada_shop
    SET access_token = 'dummy',
        refresh_token = 'dummy',
        app_secret = 'dummy';
