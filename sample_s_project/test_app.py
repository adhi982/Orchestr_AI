"""Test for add function in app module."""
from sample_s_project.app import add

def test_add():
    """Test add function with simple values."""
    assert add(2, 3) == 5 