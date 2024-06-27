"""
Theil-Sen linear regression estimator for 2D data points.\n
Very robust to outliers
"""

import numpy as np

class TheilSenPoint:
    def __init__(self, x, y, n_points):
        """
        Parameters:
        - x (float): The independant variable
        - y (float): The depenant variable
        - n_points (int): The maximum number of children that can be added to this point
        """
        # Store point
        self.x = x
        self.y = y

        # Create an empty slope list
        self._slopes = np.zeros(n_points-1)
        self._n_slopes = 0

    def add_child(self, other):
        """
        Introcude a new point to this point so that a pairwise slope can be calculated.
        
        Parameters:
        - other (TheilSenPoint): The new point to be introduced

        Notes: This method will attempt to add the child even if no space is available, so be careful
        """
        dx = other.x - self.x
        slope = (other.y - self.y) / (1e-6 if dx==0 else dx)
        self._slopes[self._n_slopes] = slope
        self._n_slopes += 1

    @property
    def valid_slopes(self):
        """
        Returns (tuple):
        - (int): The number of pairwise slopes
        - (numpy.ndarray): The list of pairwise slopes
        """
        return self._n_slopes, self._slopes[:self._n_slopes]



class TheilSen:
    """An incremental implementation of the Theil-Sen slope estimator"""

    def __init__(self, n_points, max_pairs=1000):
        """
        Parameters:
        - n_points (int): The maximum number of points to retain (queue size)
        - max_pairs (int): Maximum number of pairwise slopes to consider. If max_pairs < ~n^2/2, the slopes will be randomly sampled
        """
        self._max_points = n_points
        self._max_pairs = max_pairs

        self._points = []
        self._n_points = 0
        

    def add_point(self, x, y):
        """
        Add a new point to the estimator.
        
        Parameters:
        - x (float): The independant variable
        - y (float): The depenant variable
        """
        # Create new point
        new_point = TheilSenPoint(x, y, self._max_points)

        # Remove oldest point and append the new one
        if self._n_points >= self._max_points: self._points.pop(0)
        else: self._n_points += 1
        self._points.append(new_point)
        
        # Compute pairwise slopes with all old points
        for p in self._points[:-1]:
            p.add_child(new_point)


    def get_estimate(self):
        """Compute the slope estimate (median of pairwise slopes)."""
        if self._n_points <= 1: return 0.0

        # Create an empty array to hold pairwise slopes
        idx = 0
        slopes = np.zeros(int(self._n_points*(self._n_points-1)/2))
        
        # Collect all pairwise slopes
        for p in self._points[:-1]:
            count, sub_slopes = p.valid_slopes
            slopes[idx:idx+count] = sub_slopes
            idx += count

        # Randomly sample slopes if there are too many
        if len(slopes) > self._max_pairs:
            np.random.shuffle(slopes)
            slopes = slopes[:self._max_pairs]

        # Compute median slope
        return float(np.median(slopes))
    

    def full(self):
        """Return True if the buffer is full"""
        return self._n_points == self._max_points
