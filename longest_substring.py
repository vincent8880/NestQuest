def lengthOfLongestSubstring(s):
    """
    Find the length of the longest substring without repeating characters.
    
    Approach: Sliding Window with Hash Set
    Time Complexity: O(n)
    Space Complexity: O(min(m, n)) where m is the size of the charset
    """
    if not s:
        return 0
    
    char_set = set()
    left = 0
    max_length = 0
    
    for right in range(len(s)):
        # If current character is already in the set, move left pointer
        while s[right] in char_set:
            char_set.remove(s[left])
            left += 1
        
        # Add current character to set
        char_set.add(s[right])
        
        # Update max length
        max_length = max(max_length, right - left + 1)
    
    return max_length

def lengthOfLongestSubstring_optimized(s):
    """
    Optimized version using hash map to store last seen index
    Time Complexity: O(n)
    Space Complexity: O(min(m, n))
    """
    if not s:
        return 0
    
    char_map = {}  # character -> last seen index
    left = 0
    max_length = 0
    
    for right in range(len(s)):
        if s[right] in char_map and char_map[s[right]] >= left:
            # Character is in current window, move left pointer
            left = char_map[s[right]] + 1
        
        char_map[s[right]] = right
        max_length = max(max_length, right - left + 1)
    
    return max_length

# Test cases
def test_solution():
    test_cases = [
        ("abcabcbb", 3),
        ("bbbbb", 1),
        ("pwwkew", 3),
        ("", 0),
        ("a", 1),
        ("abcdef", 6),
        ("dvdf", 3)
    ]
    
    print("Testing Longest Substring Without Repeating Characters")
    print("=" * 60)
    
    for i, (input_str, expected) in enumerate(test_cases, 1):
        result1 = lengthOfLongestSubstring(input_str)
        result2 = lengthOfLongestSubstring_optimized(input_str)
        
        print(f"Test {i}:")
        print(f"  Input: '{input_str}'")
        print(f"  Expected: {expected}")
        print(f"  Method 1 (Set): {result1} {'✅' if result1 == expected else '❌'}")
        print(f"  Method 2 (Map): {result2} {'✅' if result2 == expected else '❌'}")
        print()

if __name__ == "__main__":
    test_solution()














