"""
Theil-Sen linear regression estimator for 2D data points.\n
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
    # Compute all pairwise differences
    x_diff = x[:, np.newaxis] - x
    y_diff = y[:, np.newaxis] - y

    # Select upper triangle, excluding the diagonal (all zeros)
    upper_tri_indices = np.triu_indices(len(x), k=1)
    x_diff = x_diff[upper_tri_indices]
    y_diff = y_diff[upper_tri_indices]

    # Compute all pairwise slopes
    slopes = y_diff / x_diff

    # Randomly sample slopes if there are too many
    if max_pairs < len(slopes):
        np.random.shuffle(slopes)
        slopes = slopes[:max_pairs]

    # Compute median slope
    median_slope = np.median(slopes)

    return median_slope
