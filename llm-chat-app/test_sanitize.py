#!/usr/bin/env python3
"""
Test script for sanitize_error_message function
"""
from api_utils import sanitize_error_message


def test_sanitize_error_message():
    """Test various API key patterns in error messages"""

    test_cases = [
        # Case 1: User's original error - partially masked key in brackets
        {
            'input': '[jW******************************************1b74]无效的令牌',
            'expected_pattern': '[API_KEY_HIDDEN]无效的令牌',
            'description': 'Partially masked key in brackets'
        },
        # Case 2: OpenAI style API key
        {
            'input': 'Invalid API key: sk-LGxrZUW3xh6ULiH736B3Ee9dB29a4917822b5d78612bE12d',
            'expected_pattern': 'Invalid API key: [API_KEY_HIDDEN]',
            'description': 'Full OpenAI API key'
        },
        # Case 3: Anthropic style API key
        {
            'input': 'Authentication failed with key sk-ant-api03-abc123def456',
            'expected_pattern': 'Authentication failed with key [API_KEY_HIDDEN]',
            'description': 'Anthropic API key'
        },
        # Case 4: Partially masked key without brackets
        {
            'input': 'Token jW***************1b74 is invalid',
            'expected_pattern': 'Token [API_KEY_HIDDEN] is invalid',
            'description': 'Partially masked key without brackets'
        },
        # Case 5: No sensitive info - should remain unchanged
        {
            'input': 'Connection timeout after 10 seconds',
            'expected_pattern': 'Connection timeout after 10 seconds',
            'description': 'No sensitive info'
        },
        # Case 6: Bearer token
        {
            'input': 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9',
            'expected_pattern': 'Authorization: Bearer [TOKEN_HIDDEN]',
            'description': 'Bearer token'
        }
    ]

    print("Testing sanitize_error_message function:\n")
    all_passed = True

    for i, test in enumerate(test_cases, 1):
        result = sanitize_error_message(test['input'])
        passed = result == test['expected_pattern']
        all_passed = all_passed and passed

        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"Test {i}: {test['description']}")
        print(f"  Status: {status}")
        print(f"  Input:    {test['input']}")
        print(f"  Expected: {test['expected_pattern']}")
        print(f"  Got:      {result}")
        print()

    return all_passed


if __name__ == '__main__':
    success = test_sanitize_error_message()

    if success:
        print("=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        exit(0)
    else:
        print("=" * 60)
        print("✗ Some tests failed!")
        print("=" * 60)
        exit(1)
