# Decisions

## 2026-11-27: Trivy ignore for CVE-2026-18140, expires 2027-01-31

New CVEs published after the last green run failed the image scan. Package
upgrades fixed all of them except aws-smithy-json 0.62.3, which sits in the
Rust lockfile vendored inside temporalio 1.37.0. That is the newest temporalio,
so only this one CVE is ignored, and only until 2027-01-31. After that the scan
blocks on it again. Approved by Surabhi.

Alternatives closed off: dropping temporalio, or deleting the Cargo.lock from
the image so the scanner can't see it.
