"""
Atmospheric Models for DSMC Simulations

Implements ISA, US76, and NRLMSISE-00 atmospheric models.
"""

import math
from typing import Dict

class AtmosphericCalculator:
    """Calculate atmospheric parameters at various altitudes"""

    # Physical constants
    R = 287.05           # Gas constant J/(kg·K)
    g0 = 9.80665         # Standard gravity m/s²
    k_B = 1.380649e-23   # Boltzmann constant J/K

    # ISA standard layers (0-86km)
    ISA_LAYERS = [
        {'h': 0,     'T0': 288.15, 'L': -0.0065, 'P0': 101325},     # Troposphere
        {'h': 11000, 'T0': 216.65, 'L': 0,       'P0': 22632.1},    # Stratosphere lower
        {'h': 20000, 'T0': 216.65, 'L': 0.001,   'P0': 5474.89},    # Stratosphere middle
        {'h': 32000, 'T0': 228.65, 'L': 0.0028,  'P0': 868.019},    # Stratosphere upper
        {'h': 47000, 'T0': 270.65, 'L': 0,       'P0': 110.906},    # Mesosphere lower
        {'h': 51000, 'T0': 270.65, 'L': -0.0028, 'P0': 66.9389},    # Mesosphere middle
        {'h': 71000, 'T0': 214.65, 'L': -0.002,  'P0': 3.95642},    # Mesosphere upper
        {'h': 86000, 'T0': 186.87, 'L': 0,       'P0': 0.3734}      # Thermosphere boundary
    ]

    # NRLMSISE-00 lookup table (simplified)
    NRLMSISE00_TABLE = [
        {'h': 100, 'T': 195,  'P': 3.2e-2,  'n': 1.2e19},
        {'h': 120, 'T': 360,  'P': 2.5e-3,  'n': 5.3e17},
        {'h': 150, 'T': 634,  'P': 4.5e-4,  'n': 5.0e16},
        {'h': 200, 'T': 854,  'P': 8.5e-5,  'n': 7.0e15},
        {'h': 250, 'T': 941,  'P': 2.5e-5,  'n': 2.0e15},
        {'h': 300, 'T': 976,  'P': 8.8e-6,  'n': 6.5e14},
        {'h': 400, 'T': 995,  'P': 1.4e-6,  'n': 1.0e14},
        {'h': 500, 'T': 999,  'P': 3.0e-7,  'n': 2.0e13}
    ]

    def calculate(self, altitude_km: float, model: str = 'NRLMSISE-00') -> Dict:
        """
        Calculate atmospheric parameters

        Args:
            altitude_km: Altitude in kilometers
            model: 'ISA', 'US76', 'NRLMSISE-00', or 'Custom'

        Returns:
            {
                'temperature': float (K),
                'pressure': float (Pa),
                'density': float (kg/m³),
                'number_density': float (#/m³),
                'model_used': str,
                'valid': bool
            }
        """
        if model == 'ISA':
            return self._calculate_isa(altitude_km)
        elif model == 'US76':
            return self._calculate_us76(altitude_km)
        elif model == 'NRLMSISE-00':
            return self._calculate_nrlmsise00(altitude_km)
        elif model == 'Custom':
            return None
        else:
            raise ValueError(f"Invalid model: {model}")

    def _calculate_isa(self, altitude_km: float) -> Dict:
        """ISA Standard Atmosphere (0-86km)"""
        h = altitude_km * 1000  # Convert to meters

        # Find layer
        layer = self.ISA_LAYERS[0]
        for lyr in reversed(self.ISA_LAYERS):
            if h >= lyr['h']:
                layer = lyr
                break

        h0, T0, L, P0 = layer['h'], layer['T0'], layer['L'], layer['P0']
        dh = h - h0

        # Calculate temperature and pressure
        if L == 0:
            # Isothermal layer
            T = T0
            P = P0 * math.exp(-self.g0 * dh / (self.R * T0))
        else:
            # Non-isothermal layer
            T = T0 + L * dh
            P = P0 * math.pow(T / T0, -self.g0 / (self.R * L))

        # Calculate density and number density
        rho = P / (self.R * T)
        n = P / (self.k_B * T)

        return {
            'temperature': T,
            'pressure': P,
            'density': rho,
            'number_density': n,
            'model_used': 'ISA',
            'valid': altitude_km <= 86
        }

    def _calculate_us76(self, altitude_km: float) -> Dict:
        """US76 Standard Atmosphere (0-1000km)"""
        if altitude_km <= 86:
            result = self._calculate_isa(altitude_km)
            result['model_used'] = 'US76'
            return result

        # Above 86km: exponential model
        h = altitude_km
        h0 = 86
        T0 = 186.87
        T_inf = 1000

        # Temperature asymptotically approaches 1000K
        xi = (h - h0) / 50
        T = T_inf - (T_inf - T0) * math.exp(-xi)

        # Pressure exponential decay
        P0 = 0.3734
        H = self.R * T / self.g0
        P = P0 * math.exp(-(h - h0) * 1000 / H)

        rho = P / (self.R * T)
        n = P / (self.k_B * T)

        return {
            'temperature': T,
            'pressure': P,
            'density': rho,
            'number_density': n,
            'model_used': 'US76',
            'valid': True
        }

    def _calculate_nrlmsise00(self, altitude_km: float) -> Dict:
        """NRLMSISE-00 model (simplified interpolation)"""
        if altitude_km < 100:
            result = self._calculate_us76(altitude_km)
            result['model_used'] = 'NRLMSISE-00 (US76 <100km)'
            return result

        # Interpolate in lookup table
        table = self.NRLMSISE00_TABLE

        if altitude_km <= table[0]['h']:
            data = table[0]
        elif altitude_km >= table[-1]['h']:
            data = table[-1]
        else:
            # Linear interpolation
            for i in range(len(table) - 1):
                if table[i]['h'] <= altitude_km < table[i+1]['h']:
                    lower, upper = table[i], table[i+1]
                    t = (altitude_km - lower['h']) / (upper['h'] - lower['h'])

                    T = lower['T'] + t * (upper['T'] - lower['T'])
                    P = lower['P'] * math.pow(upper['P'] / lower['P'], t)
                    n = lower['n'] * math.pow(upper['n'] / lower['n'], t)

                    rho = P / (self.R * T)

                    return {
                        'temperature': T,
                        'pressure': P,
                        'density': rho,
                        'number_density': n,
                        'model_used': 'NRLMSISE-00',
                        'valid': True
                    }

        # Fallback for exact table match
        T = data['T']
        P = data['P']
        n = data['n']
        rho = P / (self.R * T)

        return {
            'temperature': T,
            'pressure': P,
            'density': rho,
            'number_density': n,
            'model_used': 'NRLMSISE-00',
            'valid': True
        }
