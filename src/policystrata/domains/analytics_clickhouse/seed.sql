insert into projects values
  ('project_acme_mobile', 'org_acme', 'Acme Mobile', 'America/Los_Angeles'),
  ('project_beta_web', 'org_beta', 'Beta Web', 'UTC');

insert into sessions values
  ('project_acme_mobile', 'sess_acme_1', 'user_acme_1', '2026-06-18 08:00:00'),
  ('project_acme_mobile', 'sess_acme_2', 'user_acme_2', '2026-06-18 09:00:00'),
  ('project_acme_mobile', 'sess_acme_3', 'user_acme_1', '2026-06-19 10:00:00'),
  ('project_beta_web', 'sess_beta_1', 'user_beta_1', '2026-06-18 11:00:00');

insert into events values
  ('project_acme_mobile', 'legacy_acme', 'evt_acme_1', 'sess_acme_1', 'user_acme_1', 'page_view', 'cohort_large', 'US', 'ios', '2026-06-18 08:01:00'),
  ('project_acme_mobile', 'legacy_acme', 'evt_acme_2', 'sess_acme_1', 'user_acme_1', 'purchase', 'cohort_large', 'US', 'ios', '2026-06-18 08:04:00'),
  ('project_acme_mobile', 'legacy_acme', 'evt_acme_3', 'sess_acme_2', 'user_acme_2', 'page_view', 'cohort_small', 'CA', 'android', '2026-06-18 09:02:00'),
  ('project_acme_mobile', 'legacy_acme', 'evt_acme_4', 'sess_acme_3', 'user_acme_1', 'return', 'cohort_large', 'US', 'ios', '2026-06-19 10:02:00'),
  ('project_beta_web', 'legacy_beta', 'evt_beta_1', 'sess_beta_1', 'user_beta_1', 'page_view', 'cohort_large', 'GB', 'web', '2026-06-18 11:01:00');
