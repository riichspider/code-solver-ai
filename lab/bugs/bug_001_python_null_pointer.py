"""
Bug: Python NoneType null pointer exception
Description: Function fails when input is None without proper validation
Expected error: AttributeError: 'NoneType' object has no attribute 'split'
"""

def process_user_data(user_input):
    """
    Process user input and return the first word
    Bug: No validation for None input
    """
    # This will fail if user_input is None
    words = user_input.split()
    return words[0] if words else ""

def main():
    # Test cases
    test_cases = [
        "hello world",  # Normal case
        "",             # Empty string
        None,           # Bug trigger
    ]
    
    for i, test_case in enumerate(test_cases):
        try:
            result = process_user_data(test_case)
            print(f"Test {i+1}: '{test_case}' -> '{result}'")
        except Exception as e:
            print(f"Test {i+1}: '{test_case}' -> ERROR: {e}")

if __name__ == "__main__":
    main()

# TODO: enviar para o pipeline com: python main.py "Python NoneType exception in process_user_data function - need to add null validation"
