DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
            AND table_name = 'api_tokens'
            AND column_name = 'token'
    ) THEN
        EXECUTE $sql$
            DELETE FROM api_tokens
            WHERE uuid = '30000000-0000-4000-8000-000000000001'
                OR token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1dWlkIjoiMzAwMDAwMDAtMDAwMC00MDAwLTgwMDAtMDAwMDAwMDAwMDAxIiwidXNlcm5hbWUiOm51bGwsInJvbGUiOiJBUEkiLCJpYXQiOjAsImV4cCI6OTk5OTk5OTk5OX0.ILbG2DvyxMN6m7zGXYmaUTd1gbZsRDJHFYLc_yZQjgY'
        $sql$;

        EXECUTE $sql$
            INSERT INTO api_tokens (uuid, token, token_name)
            VALUES (
                '30000000-0000-4000-8000-000000000001',
                'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1dWlkIjoiMzAwMDAwMDAtMDAwMC00MDAwLTgwMDAtMDAwMDAwMDAwMDAxIiwidXNlcm5hbWUiOm51bGwsInJvbGUiOiJBUEkiLCJpYXQiOjAsImV4cCI6OTk5OTk5OTk5OX0.ILbG2DvyxMN6m7zGXYmaUTd1gbZsRDJHFYLc_yZQjgY',
                'Mini Shop local QA token'
            )
            ON CONFLICT (token) DO UPDATE SET
                token_name = EXCLUDED.token_name,
                updated_at = now()
        $sql$;
    ELSE
        EXECUTE $sql$
            DELETE FROM api_tokens
            WHERE uuid = '30000000-0000-4000-8000-000000000001'
        $sql$;

        EXECUTE $sql$
            INSERT INTO api_tokens (uuid, name, scopes, expire_at)
            VALUES (
                '30000000-0000-4000-8000-000000000001',
                'Mini Shop local QA token',
                ARRAY['*'],
                now() + interval '99999 days'
            )
            ON CONFLICT (uuid) DO UPDATE SET
                name = EXCLUDED.name,
                scopes = EXCLUDED.scopes,
                expire_at = EXCLUDED.expire_at,
                updated_at = now()
        $sql$;
    END IF;
END $$;

WITH upserted_users AS (
    INSERT INTO users (
        uuid,
        short_uuid,
        username,
        status,
        traffic_limit_bytes,
        traffic_limit_strategy,
        expire_at,
        trojan_password,
        vless_uuid,
        ss_password,
        description,
        email,
        telegram_id,
        hwid_device_limit,
        tag,
        last_triggered_threshold,
        updated_at
    ) VALUES
        (
            '00000000-0000-4000-8000-000000000001',
            'devadmin01',
            'runes_admin',
            'ACTIVE',
            107374182400,
            'NO_RESET',
            now() + interval '20 days',
            'dev-trojan-admin',
            '20000000-0000-4000-8000-000000000001',
            'dev-ss-admin',
            'Mini Shop local QA active standard user',
            'runes.admin@example.com',
            910000001,
            3,
            'mini-shop-dev',
            0,
            now()
        ),
        (
            '00000000-0000-4000-8000-000000000002',
            'devactive1',
            'runes_active',
            'LIMITED',
            214748364800,
            'NO_RESET',
            now() + interval '55 days',
            'dev-trojan-active',
            '20000000-0000-4000-8000-000000000002',
            'dev-ss-active',
            'Mini Shop local QA active premium user near traffic limit',
            'runes.active@example.com',
            910000002,
            5,
            'mini-shop-dev',
            80,
            now()
        ),
        (
            '00000000-0000-4000-8000-000000000003',
            'devexpired',
            'runes_expired',
            'EXPIRED',
            53687091200,
            'NO_RESET',
            now() - interval '15 days',
            'dev-trojan-expired',
            '20000000-0000-4000-8000-000000000003',
            'dev-ss-expired',
            'Mini Shop local QA expired user',
            'runes.expired@example.com',
            910000003,
            1,
            'mini-shop-dev',
            100,
            now()
        )
    ON CONFLICT (uuid) DO UPDATE SET
        short_uuid = EXCLUDED.short_uuid,
        username = EXCLUDED.username,
        status = EXCLUDED.status,
        traffic_limit_bytes = EXCLUDED.traffic_limit_bytes,
        traffic_limit_strategy = EXCLUDED.traffic_limit_strategy,
        expire_at = EXCLUDED.expire_at,
        trojan_password = EXCLUDED.trojan_password,
        vless_uuid = EXCLUDED.vless_uuid,
        ss_password = EXCLUDED.ss_password,
        description = EXCLUDED.description,
        email = EXCLUDED.email,
        telegram_id = EXCLUDED.telegram_id,
        hwid_device_limit = EXCLUDED.hwid_device_limit,
        tag = EXCLUDED.tag,
        last_triggered_threshold = EXCLUDED.last_triggered_threshold,
        updated_at = now()
    RETURNING t_id
),
default_squad AS (
    SELECT uuid
    FROM internal_squads
    WHERE name = 'Default-Squad'
    LIMIT 1
)
INSERT INTO internal_squad_members (internal_squad_uuid, user_id)
SELECT default_squad.uuid, upserted_users.t_id
FROM default_squad
CROSS JOIN upserted_users
ON CONFLICT DO NOTHING;

INSERT INTO user_traffic (
    t_id,
    used_traffic_bytes,
    lifetime_used_traffic_bytes,
    online_at,
    first_connected_at
)
SELECT
    t_id,
    CASE username
        WHEN 'runes_admin' THEN 21474836480
        WHEN 'runes_active' THEN 193273528320
        ELSE 53687091200
    END,
    CASE username
        WHEN 'runes_admin' THEN 32212254720
        WHEN 'runes_active' THEN 214748364800
        ELSE 53687091200
    END,
    CASE WHEN username = 'runes_expired' THEN null ELSE now() - interval '5 minutes' END,
    now() - interval '30 days'
FROM users
WHERE username IN ('runes_admin', 'runes_active', 'runes_expired')
ON CONFLICT (t_id) DO UPDATE SET
    used_traffic_bytes = EXCLUDED.used_traffic_bytes,
    lifetime_used_traffic_bytes = EXCLUDED.lifetime_used_traffic_bytes,
    online_at = EXCLUDED.online_at,
    first_connected_at = EXCLUDED.first_connected_at;
