import pytest
from atmospheric_models import AtmosphericCalculator

def test_nrlmsise00_at_80km():
    """Test NRLMSISE-00 model at 80km altitude"""
    calc = AtmosphericCalculator()

    result = calc.calculate(altitude_km=80, model='NRLMSISE-00')

    assert result['model_used'] == 'NRLMSISE-00 (US76 <100km)'
    assert 185 < result['temperature'] < 200  # ~187K at 80km
    assert 0.3 < result['pressure'] < 1.5     # ~0.37 Pa at 80km
    assert result['density'] > 0
    assert result['number_density'] > 0

def test_isa_below_86km():
    """Test ISA model below 86km"""
    calc = AtmosphericCalculator()

    result = calc.calculate(altitude_km=50, model='ISA')

    assert result['model_used'] == 'ISA'
    assert result['valid'] == True
    assert result['temperature'] > 0
    assert result['pressure'] > 0

def test_invalid_model_name():
    """Test error handling for invalid model"""
    calc = AtmosphericCalculator()

    with pytest.raises(ValueError):
        calc.calculate(altitude_km=50, model='INVALID')
