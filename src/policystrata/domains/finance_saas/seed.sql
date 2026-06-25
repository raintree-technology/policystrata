insert into advisors (id, firm_id, name, region) values
    ('adv_north_1', 'north', 'North Advisory', 'west'),
    ('adv_south_1', 'south', 'South Advisory', 'east');

insert into households (id, firm_id, legacy_firm_id, advisor_id, name, tax_id, segment) values
    ('hh_north_1', 'north', 'legacy_north', 'adv_north_1', 'North Family Office', '111-22-3333', 'high_net_worth'),
    ('hh_north_2', 'north', 'legacy_north', 'adv_north_1', 'North Growth Trust', '222-33-4444', 'mass_affluent'),
    ('hh_south_1', 'south', 'legacy_south', 'adv_south_1', 'South Retirement Plan', '333-44-5555', 'retirement');

insert into accounts (id, household_id, account_type) values
    ('acct_north_1', 'hh_north_1', 'taxable'),
    ('acct_north_2', 'hh_north_2', 'ira'),
    ('acct_south_1', 'hh_south_1', 'taxable');

insert into transactions (
    id,
    account_id,
    transaction_date,
    transaction_type,
    amount_cents,
    gross_amount_cents,
    fee_cents
) values
    ('txn_north_1', 'acct_north_1', date '2026-05-06', 'deposit', 150000, 175000, 12000),
    ('txn_north_2', 'acct_north_2', date '2026-05-14', 'withdrawal', -25000, 25000, 5500),
    ('txn_south_1', 'acct_south_1', date '2026-05-09', 'deposit', 90000, 100000, 8000);

insert into balances (id, account_id, balance_date, market_value_cents) values
    ('bal_north_1', 'acct_north_1', date '2026-05-31', 1750000),
    ('bal_north_2', 'acct_north_2', date '2026-05-31', 750000),
    ('bal_south_1', 'acct_south_1', date '2026-05-31', 600000);
