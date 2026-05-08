import re

# Teste da regex do método _add_colon
code = "def my_function()\n    print('hello')"
pattern = r'(def|class|if|for|while|try|with)([^\n:]+)\s*$'

print("Código original:")
repr(code)
print(f"\nPattern: {pattern}")

# Teste com flags MULTILINE
matches = re.search(pattern, code, flags=re.MULTILINE)
print(f"\nMatches com MULTILINE: {matches}")

if matches:
    print(f"Groups: {matches.groups()}")
    print(f"Match: '{matches.group(0)}'")

# Teste sem flags
matches_no_flags = re.search(pattern, code)
print(f"\nMatches sem flags: {matches_no_flags}")

# Teste linha por linha
print("\nTeste linha por linha:")
for i, line in enumerate(code.split('\n')):
    match = re.search(pattern, line)
    print(f"Linha {i}: '{line}' -> Match: {match}")
