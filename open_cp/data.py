"""Encapsulates input data."""

import numpy as _np

class Point():
    def __init__(self, x=0, y=0):
        self._x = x
        self._y = y

    @property
    def x(self):
        return self._x

    @property
    def y(self):
        return self._y

    def __add__(self, other):
        return Point(self.x + other.x, self.y + other.y)

    def __repr__(self):
        return "Point({},{})".format(self.x, self.y)


class RectangularRegion():
    def __init__(self, xmin=0, xmax=1, ymin=0, ymax=1):
        self._min = Point(xmin, ymin)
        self._max = Point(xmax, ymax)

    @property
    def xmin(self):
        return self._min.x

    @property
    def xmax(self):
        return self._max.x

    @property
    def ymin(self):
        return self._min.y

    @property
    def ymax(self):
        return self._max.y

    @property
    def min(self):
        return self._min

    @property
    def max(self):
        return self._max

    @property
    def aspect_ratio(self):
        if self.xmax == self.xmin:
            return _np.nan
        return (self.ymax - self.ymin) / (self.xmax - self.xmin)

    def __add__(self, other):
        return RectangularRegion(xmin = self.xmin + other.x,
                                 xmax = self.xmax + other.x,
                                 ymin = self.ymin + other.y,
                                 ymax = self.ymax + other.y)

    def grid_size(self, cell_width, cell_height = None):
        if cell_height is None:
            cell_height = cell_width
        xsize = int(_np.rint((self.xmax - self.xmin) / cell_width))
        ysize = int(_np.rint((self.ymax - self.ymin) / cell_height))
        return xsize, ysize

    def __repr__(self):
        return "RectangularRegion( ({},{}) -> ({},{}) )".format(self.xmin,
                                 self.ymin, self.xmax, self.ymax)


class TimedPoints:
    """Stores a list of timestamped x-y coordinates of events"""

    @staticmethod
    def _is_time_ordered(timestamps):
        if len(timestamps) == 0:
            return True
        it = iter(timestamps)
        prev = next(it)
        for time in it  :
            if prev > time:
                return False
            prev = time
        return True

    def _assert_times_ordered(self, timestamps):
        if not self._is_time_ordered(timestamps):
            raise ValueError("Input must be time ordered")

    def __init__(self, timestamps, coords):
        self._assert_times_ordered(timestamps)
        self.timestamps = _np.array(timestamps, dtype="datetime64[ms]")
        self.coords = _np.array(coords).astype(_np.float64)
        if len(self.coords.shape) != 2 or self.coords.shape[0] != 2:
            raise Exception("Coordinates should be of shape (2,#)")
        if len(self.timestamps) != self.coords.shape[1]:
            raise Exception("Input data should all be of the same length")

    @property
    def xcoords(self):
        return self.coords[0]

    @property
    def ycoords(self):
        return self.coords[1]
        
    def __getitem__(self, index):
        if isinstance(index, int):
            return [self.timestamps[index], *self.coords[:, index]]
        # Assume slice like object
        new_times = self.timestamps[index]
        new_coords = self.coords[:,index]
        if self._is_time_ordered(new_times):
            return TimedPoints(new_times, new_coords)
        data = [(t,x,y) for t, (x,y) in zip(new_times, new_coords.T)]
        data.sort(key = lambda triple : triple[0])
        for i, (t,x,y) in enumerate(data):
            new_times[i] = t
            new_coords[0,i] = x
            new_coords[1,i] = y
        return TimedPoints(new_times, new_coords)

    def events_before(self, cutoff_time):
        mask = self.timestamps <= cutoff_time
        return TimedPoints(self.timestamps[mask], self.coords[:,mask])

    @property
    def empty(self):
        return len(self.timestamps) == 0
    
    @property
    def number_data_points(self):
        return len(self.timestamps)

    @property
    def bounding_box(self):
        return RectangularRegion(xmin = _np.min(self.xcoords),
            xmax = _np.max(self.xcoords), ymin = _np.min(self.ycoords),
            ymax = _np.max(self.ycoords))

    @property
    def time_range(self):
        """Find the time range.

        :return: A pair (start, end) of timestamps.
        """
        return ( self.timestamps[0], self.timestamps[-1] )

    def time_deltas(self, time_unit = _np.timedelta64(1, "m")):
        """Returns a numpy array of floats, converted from the timestamps,
        starting from 0, and with the optional unit.

        :param time_unit: The unit to measure time by.  Defaults to 1 minute,
        so timestamps an hour apart will be converted to floats 60.0 apart.
        No rounding occurs, so there is no loss in accuracy by passing a
        different time unit.
        """
        return ( self.timestamps - self.timestamps[0] ) / time_unit

    def to_time_space_coords(self, time_unit = _np.timedelta64(1, "m")):
        """Returns a single numpy array `[t,x,y]` where the time stamps are
        converted to floats, starting from 0, and with the optional unit.

        :param time_unit: The unit to measure time by.  Defaults to 1 minute,
        so timestamps an hour apart will be converted to floats 60.0 apart.
        No rounding occurs, so there is no loss in accuracy by passing a
        different time unit.
        """
        times = self.time_deltas(time_unit)
        return np.vstack([times, self.xcoords, self.ycoords])

    @staticmethod
    def from_coords(timestamps, xcoords, ycoords):
        lengths = { len(timestamps), len(xcoords), len(ycoords) }
        if len(lengths) != 1:
            raise Exception("Input data should all be of the same length")
        return TimedPoints(timestamps, _np.stack([xcoords, ycoords]))


try:
    import pyproj as _proj
except ModuleNotFoundError:
    import sys
    print("Package 'pyproj' not found: projection methods will not be supported.", file=sys.stderr)
    _proj = None

# http://spatialreference.org/ref/epsg/
# 7405 is suitable for UK
def points_from_lon_lat(points, proj=None, epsg=None):
    if not _proj:
        return points
    if not proj:
        if not epsg:
            raise Exception("Need to provide one of 'proj' object or 'epsg' code")
        proj = _proj.Proj({"init": "epsg:"+str(epsg)})
    
    transformed = _np.empty(points.coords.shape)
    for i in range(len(points.timestamps)):
        transformed[0][i], transformed[1][i] = proj(points.xcoords[i], points.ycoords[i])
    
    return TimedPoints(points.timestamps, transformed)
