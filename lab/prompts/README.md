# Prompts

**Purpose**: Store, test, and optimize prompts for different AI models and use cases.

## Template for New Prompts

```markdown
# [Prompt Name]

**Date**: YYYY-MM-DD  
**Model**: [model-name]  
**Purpose**: [classification|generation|reasoning|repair|validation]  
**Status**: [draft|testing|stable|deprecated]

## Prompt
```
[Insert prompt text here]
```

## Variables
- `{variable1}`: Description
- `{variable2}`: Description

## Test Cases
1. Input: Example input → Expected: Expected output
2. Input: Example input → Expected: Expected output

## Performance
- Accuracy: [percentage]%
- Consistency: [high|medium|low]
- Token usage: [average tokens]

## Notes
Observations, limitations, or improvements needed.

## Variations
Alternative versions or optimizations.
```

## Usage

1. Create a new file for each prompt
2. Use purpose-based filenames (e.g., `classification-python-bugs.md`)
3. Test prompts with different inputs
4. Track performance metrics
5. Update status based on results
