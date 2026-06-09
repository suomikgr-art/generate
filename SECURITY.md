# Security Policy

## Supported Versions

This project is currently maintained on the `main` branch.

| Version / Branch | Supported |
| --- | --- |
| `main` (latest) | Yes |
| Older commits / forks | No |

If a tagged release process is introduced later, this table will be updated to include specific version ranges.

## Reporting a Vulnerability

If you discover a security issue in this repository, please report it responsibly.

1. Do not open a public issue with exploit details.
2. Use GitHub Security Advisories (private report):
   - Go to the repository `Security` tab.
   - Click `Report a vulnerability`.
3. If Security Advisories are unavailable, open a minimal issue without sensitive details and request a private contact channel.

## What to Include in a Report

Please provide as much of the following as possible:

- A clear description of the vulnerability.
- Affected file(s), function(s), and code path(s).
- Reproduction steps or proof of concept.
- Expected behavior vs actual behavior.
- Impact assessment (confidentiality, integrity, availability).
- Suggested mitigation (optional).

## Response Timeline

- Initial acknowledgment: within 3 business days.
- Triage and severity assessment: within 7 business days.
- Fix plan or mitigation guidance: as soon as validated.

Complex reports may take longer to fully remediate depending on reproducibility and impact.

## Scope

In scope:

- Vulnerabilities in repository source code and project-managed dependencies.
- Security flaws that could affect users running this project from source.

Out of scope:

- Vulnerabilities in third-party services or infrastructure not controlled by this repository.
- Issues caused by modified forks or untrusted local environments.
- Requests for support unrelated to security vulnerabilities.

## Disclosure Policy

Please allow time for verification and patching before public disclosure.

After a fix is available, maintainers may publish:

- A summary of the vulnerability,
- Affected versions/commits,
- Remediation guidance.

## Security Best Practices for Users

- Keep dependencies updated (`requirements.txt`).
- Run this project in an isolated environment (virtualenv/venv).
- Do not expose local runtime or generated data directories publicly.
- Review network and endpoint usage in your environment before deployment.
