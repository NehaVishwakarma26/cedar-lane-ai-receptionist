import utils

def test_phone():
    # Indian mobile numbers (E.164 format: +91 followed by 10 digits starting with 6-9)
    assert utils.normalize_phone("9876543210") == "+919876543210"
    assert utils.normalize_phone("098765 43210") == "+919876543210"
    assert utils.normalize_phone("+91 98765-43210") == "+919876543210"
    assert utils.normalize_phone("919876543210") == "+919876543210"
    
    # International numbers (retained for robustness)
    assert utils.normalize_phone("+44 20 7946 0958") == "+442079460958"
    
    # Invalid numbers / edge cases
    assert utils.normalize_phone("123") is None
    assert utils.normalize_phone("5876543210") is None  # Doesn't start with valid Indian mobile prefix (6-9)
    assert utils.normalize_phone("") is None


def test_strip_think():
    assert utils.strip_think("<think>hmm\nlines</think>Hello") == "Hello"
    assert utils.strip_think("Hi <think>unclosed") == "Hi"
    assert utils.strip_think("plain") == "plain"