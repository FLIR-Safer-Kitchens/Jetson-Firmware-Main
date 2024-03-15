"""
Theil-Sen linear regression estimator for 2D data points.

Very robust to outliers
"""

import numpy as np

def theil_sen(x, y, max_pairs=1000):
    """
    Compute the slope of a line using the Theil-Sen estimator

    Parameters:
    - x (numpy.ndarray): Independent variable values (column vector)
    - y (numpy.ndarray): Dependent variable values (column vector)
    - max_pairs (int): Maximum number of pairwise slopes to consider

    Returns: float
        Theil-Sen estimate of the slope.
    """
    # Compute all pairwise slopes
    slopes = (y[:, np.newaxis] - y) / (x[:, np.newaxis] - x)

    # Filter out infinite slopes (where x values are identical)
    finite_slopes = slopes[np.isfinite(slopes)]
    
    # Randomly sample slopes if there are too many
    if max_pairs < len(finite_slopes):
        np.random.shuffle(finite_slopes)
        finite_slopes = finite_slopes[:max_pairs]
    
    # Compute median slope
    median_slope = np.median(finite_slopes)

    return median_slope
