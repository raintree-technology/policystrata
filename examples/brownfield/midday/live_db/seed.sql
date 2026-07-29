-- SYNTHESIZED. Not midday data.
--
-- Two teams with one member each, and rows on both sides of every real policy in
-- schema_scoped.sql. The point of the shape is that each table holds at least one row the
-- querying principal must not see: if midday's policies were dropped or weakened, a check would
-- return the other team's row and the containment assertion would fail. Values are fixed so the
-- fixture is deterministic.
--
-- UUIDs are chosen to be readable in output:
--   team acme = 1111..., team beta = 2222...
--   user ann (acme) = aaaa..., user ben (beta) = bbbb...

INSERT INTO teams (id, name) VALUES
    ('11111111-1111-1111-1111-111111111111', 'acme'),
    ('22222222-2222-2222-2222-222222222222', 'beta');

INSERT INTO users (id, email) VALUES
    ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'ann@acme.example'),
    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'ben@beta.example');

INSERT INTO users_on_team (user_id, team_id) VALUES
    ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '11111111-1111-1111-1111-111111111111'),
    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', '22222222-2222-2222-2222-222222222222');

INSERT INTO customers (id, team_id, name) VALUES
    ('c1111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111111', 'acme customer'),
    ('c2222222-2222-2222-2222-222222222222', '22222222-2222-2222-2222-222222222222', 'beta customer');

-- Two insights per team, same period coordinates on both sides so a missing team predicate
-- returns twice the rows rather than a different-looking result.
INSERT INTO insights (
    id, team_id, period_type, period_start, period_end, period_year, period_number,
    status, currency, generated_at
) VALUES
    ('d1111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111111',
     'monthly', '2026-05-01T00:00:00Z', '2026-05-31T23:59:59Z', 2026, 5,
     'completed', 'USD', '2026-06-01T00:00:00Z'),
    ('d1111111-1111-1111-1111-111111111112', '11111111-1111-1111-1111-111111111111',
     'monthly', '2026-06-01T00:00:00Z', '2026-06-30T23:59:59Z', 2026, 6,
     'completed', 'USD', '2026-07-01T00:00:00Z'),
    ('d2222222-2222-2222-2222-222222222221', '22222222-2222-2222-2222-222222222222',
     'monthly', '2026-05-01T00:00:00Z', '2026-05-31T23:59:59Z', 2026, 5,
     'completed', 'EUR', '2026-06-01T00:00:00Z'),
    ('d2222222-2222-2222-2222-222222222222', '22222222-2222-2222-2222-222222222222',
     'monthly', '2026-06-01T00:00:00Z', '2026-06-30T23:59:59Z', 2026, 6,
     'completed', 'EUR', '2026-07-01T00:00:00Z');

-- insight_user_status is scoped by user_id = auth.uid(), not by team. It is included because it
-- is the one traced table whose real policy uses a different dimension: a fixture that only
-- tested team scoping would not notice a checker that assumed every table is team-scoped.
INSERT INTO insight_user_status (insight_id, user_id, read_at) VALUES
    ('d1111111-1111-1111-1111-111111111111', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
     '2026-06-02T09:00:00Z'),
    ('d2222222-2222-2222-2222-222222222221', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
     '2026-06-02T10:00:00Z');

INSERT INTO invoice_recurring (
    id, team_id, user_id, customer_id, frequency, end_type, status, timezone, amount, currency
) VALUES
    ('e1111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111111',
     'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'c1111111-1111-1111-1111-111111111111',
     'monthly_date', 'never', 'active', 'UTC', 1000.00, 'USD'),
    ('e2222222-2222-2222-2222-222222222222', '22222222-2222-2222-2222-222222222222',
     'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'c2222222-2222-2222-2222-222222222222',
     'weekly', 'never', 'active', 'UTC', 2000.00, 'EUR');

INSERT INTO platform_identities (
    id, provider, team_id, user_id, external_user_id, external_team_id
) VALUES
    ('f1111111-1111-1111-1111-111111111111', 'slack',
     '11111111-1111-1111-1111-111111111111', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
     'U-ACME-ANN', 'T-ACME'),
    ('f2222222-2222-2222-2222-222222222222', 'slack',
     '22222222-2222-2222-2222-222222222222', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
     'U-BETA-BEN', 'T-BETA');

INSERT INTO platform_link_tokens (
    id, code, provider, team_id, user_id, expires_at
) VALUES
    ('a1111111-1111-1111-1111-111111111111', 'link-acme', 'slack',
     '11111111-1111-1111-1111-111111111111', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
     '2027-01-01T00:00:00Z'),
    ('a2222222-2222-2222-2222-222222222222', 'link-beta', 'slack',
     '22222222-2222-2222-2222-222222222222', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
     '2027-01-01T00:00:00Z');

INSERT INTO provider_notification_batches (
    id, batch_key, platform_identity_id, team_id, user_id, provider, event_family, payload,
    window_ends_at
) VALUES
    ('b1111111-1111-1111-1111-111111111111', 'batch-acme',
     'f1111111-1111-1111-1111-111111111111',
     '11111111-1111-1111-1111-111111111111', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
     'slack', 'invoice', '{}', '2026-08-01T00:00:00Z'),
    ('b2222222-2222-2222-2222-222222222222', 'batch-beta',
     'f2222222-2222-2222-2222-222222222222',
     '22222222-2222-2222-2222-222222222222', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
     'slack', 'invoice', '{}', '2026-08-01T00:00:00Z');
