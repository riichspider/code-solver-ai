# Security Policy

## Supported Versions

| Version | Supported          | Status |
| ------- | ------------------ | ------ |
| 0.1.x   | :white_check_mark: | Beta  |
| < 0.1   | :x:                | N/A    |

**Note**: Code Solver AI is currently in beta version (0.1.0). Security updates are provided for the current beta version.

## Reporting a Vulnerability

### How to Report

If you discover a security vulnerability in Code Solver AI, please report it responsibly:

1. **Create a GitHub Issue** with the `security` label
2. **Title**: Start with `[SECURITY]` - e.g., `[SECURITY] Code injection vulnerability`
3. **Description**: Include:
   - Detailed description of the vulnerability
   - Steps to reproduce the issue
   - Potential impact assessment
   - Any suggested mitigations (if known)

### What to Expect

- **Response Time**: We'll acknowledge receipt within 48 hours
- **Assessment**: We'll evaluate the vulnerability within 7 business days
- **Resolution**: If accepted, we'll aim to release a fix in the next version
- **Disclosure**: We'll coordinate disclosure timing with you

### Security Considerations

Code Solver AI is designed with security in mind:

- **Local Execution**: All code execution happens in isolated sandboxes
- **No External APIs**: Project works completely offline
- **Input Validation**: User inputs are validated before processing
- **Cache Isolation**: Cache files are stored securely with TTL

### Private Reporting

For sensitive vulnerabilities, you can also report privately by:
- Creating a private GitHub Issue (only project maintainers can see)
- Contacting maintainers directly through GitHub

Thank you for helping keep Code Solver AI secure! 🛡️
