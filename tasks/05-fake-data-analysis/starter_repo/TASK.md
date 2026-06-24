# Campaign Lift Trust Review

Marketing leadership wants an executive-ready readout on whether a recent campaign appears to have improved performance.

Before writing the summary, audit the supplied data and decide what level of claim the data can support.

Deliverables:
- `outputs/trust_report.json`
- `outputs/executive_summary.md`

The trust report should include:
- `causal_claim_allowed`
- `confident_lift_claim`
- `data_quality_blockers`
- `supported_findings`
- `unsupported_claims`
- `verification_notes`

`data_quality_blockers` should be structured objects with:
- `theme`
- `evidence`
- `impact`

The executive summary should be suitable for leadership, but it must not overstate the evidence. If the data has issues that prevent a confident lift or causal claim, say that clearly and explain why.

Run `./VERIFY.sh` before you finish.
