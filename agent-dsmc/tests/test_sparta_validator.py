import pytest
from sparta_validator import SpartaValidator

def test_validate_valid_input():
    """Test validation of a valid SPARTA input"""
    validator = SpartaValidator()

    content = """
dimension 3
create_box 0 10 0 5 0 5
create_grid 100 50 50
species air.species N2 O2
    """

    result = validator.validate(content)

    assert result['valid'] == True
    assert len(result['errors']) == 0

def test_validate_missing_required_command():
    """Test validation fails when required command missing"""
    validator = SpartaValidator()

    content = """
dimension 3
create_box 0 10 0 5 0 5
    """

    result = validator.validate(content)

    assert result['valid'] == False
    assert 'create_grid' in str(result['errors'])

def test_validate_invalid_dimension():
    """Test validation catches invalid dimension"""
    validator = SpartaValidator()

    content = """
dimension 5
create_box 0 10 0 5 0 5
create_grid 100 50 50
species air.species N2 O2
    """

    result = validator.validate(content)

    assert result['valid'] == False
    assert 'dimension' in str(result['errors']).lower()
