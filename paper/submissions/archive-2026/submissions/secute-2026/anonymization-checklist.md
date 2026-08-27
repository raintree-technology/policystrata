# SECUTE 2026 Anonymization Checklist

Use this before creating the HotCRP submission PDF or artifact link.

## Remove From Paper

- Zachary Roth.
- Raintree Technology.
- `admin@raintree.technology`.
- Personal email addresses.
- Raintree URLs.
- Public GitHub owner names.
- Public PolicyStrata release URLs that identify the author.
- BetterOff name, repository path, app screenshots, or household-finance details that identify the
  author or company.
- Acknowledgments.
- PDF metadata that includes author, company, local filesystem path, or build user.

## Replace With Anonymous Terms

- `PolicyStrata` may remain as the tool name unless the public package makes anonymity impossible;
  otherwise use `the tool` in the submission and restore the name after review.
- BetterOff becomes `a brownfield personal-finance application fixture`.
- Raintree becomes `the authors' organization` only if needed; otherwise omit.
- Public release links become `anonymous artifact repository`.

## Artifact Rules

- Create a fresh anonymous archive or repository.
- Remove git history.
- Remove author-owned CI badges, package-publishing metadata, personal domains, and issue templates.
- Keep deterministic tests and scripts.
- Keep license if allowed, but avoid copyright holder names that identify the author.
- Use synthetic fixture data only.
- Include the reproduction command and expected output.

## Final Checks

- `pdftotext` search for `Zachary`, `Raintree`, `BetterOff`, `admin@`, `mtree`, `mb1`,
  `/Users/`, `github.com/raintree`, and public preprint URLs.
- `pdfinfo` metadata check.
- `rg` over the anonymized artifact for author/company identifiers.
- Visual PDF check for readable tables and no overflow.
