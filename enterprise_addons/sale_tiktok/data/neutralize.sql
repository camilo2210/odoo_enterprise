-- neutralize TikTok Shop API credentials
UPDATE tiktok_shop
   SET tiktok_shop_ref = CONCAT('dummy_', id),
        tiktok_cipher = 'dummy',
        app_secret = 'dummy',
        service_extern_id = 'dummy',
        access_token = 'dummy',
        refresh_token = 'dummy';
