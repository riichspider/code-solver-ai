# Vulnerabilities

**Purpose**: Document and track security vulnerabilities, potential exploits, and security improvements.

## Template for New Vulnerability Reports

```markdown
# [Vulnerability Title]

**Date**: YYYY-MM-DD  
**Status**: [discovered|investigating|patched|mitigated]  
**Severity**: [low|medium|high|critical]  
**CVSS Score**: [score if applicable]

## Description
Type of vulnerability and what it affects.

## Affected Components
Files, modules, or systems impacted.

## Proof of Concept
Code or steps demonstrating the vulnerability.

## Impact
Potential damage or risk level.

## Remediation
How to fix the vulnerability.

## Prevention
How to avoid similar vulnerabilities.

## References
Related security advisories, CVEs, or documentation.
```

## Usage

1. Create a new file for each vulnerability
2. Use severity-based filenames (e.g., `critical-2024-05-06-sql-injection.md`)
3. Update status as patches are applied
4. Review regularly for outstanding issues
