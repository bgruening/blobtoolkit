#!/usr/bin/env python3
"""
Field Class module.

Generic, identifier, variable, category, and array field types.
"""

from collections import OrderedDict
from functools import reduce
import numbers
from operator import add


class Field():
    """Parent class for specific field types."""

    __slots__ = ['field_id',
                 'values',
                 'keys',
                 'meta',
                 'type',
                 'headers',
                 'category_slot',
                 '_subset'
                 ]

    def __init__(self, field_id, **kwargs):
        """Init Field class."""
        self.field_id = field_id
        self.type = 'generic'
        self.values = []
        self.keys = []
        self.meta = {}
        self._subset = False
        self.update_data(**kwargs)

    def update_data(self, **kwargs):
        """Update values and keys for an existing field."""
        for key, value in kwargs.items():
            setattr(self, key, value)

    def update_values(self, values):
        """Update values and keys for an existing field."""
        if len(values) == len(self.values):
            self.values = values[:]

    def update_keys(self, keys):
        """Update values and keys for an existing field."""
        self.keys = keys[:]

    def get_values_by_indices(self, indices):
        """Get values for all records at matching indices."""
        values = []
        if not isinstance(indices, list):
            indices = [indices]
        for index in indices:
            try:
                values.append(self.values[index])
            except TypeError:
                pass
        return values

    def get_indices_by_values(self, values):
        """Get indices for all records matching a value."""
        if not isinstance(values, set):
            if not isinstance(values, list):
                values = [values]
            else:
                values = set(values)
        indices = [i for i, x in enumerate(self.values) if x in values]
        return indices

    def select_records(self, indices=False):
        """Create a subset of values from a list of indices."""
        values = []
        if not isinstance(indices, list):
            values = False
        else:
            values = self.get_values_by_indices(indices)
        self.subset = values
        return values

    def values_to_dict(self):
        """Create a dict of values (with keys if applicable)."""
        data = {'values': self.values}
        for key in ('keys', 'headers', 'category_slot'):
            if key in self.__slots__:
                if hasattr(self, key):
                    data[key] = getattr(self, key)
        return data

    @property
    def subset(self):
        """Subset property."""
        subset = []
        if isinstance(self._subset, list):
            subset = self._subset
        else:
            subset = self.values
        return subset

    @subset.setter
    def subset(self, values=False):
        """Set subset using indices."""
        if isinstance(values, list):
            self._subset = values
        else:
            self._subset = False

    @staticmethod
    def _collapse_values(values, keys=None):
        """
        Replace values with indices in list of keys.

        >>> Field._collapse_values(['A', 'A', 'B', 'A'])
        (['A', 'B'], [0, 0, 1, 0])
        """
        if keys is None:
            keys = []
        counter = len(keys)
        keys = OrderedDict([(key, index) for index, key in enumerate(keys)])
        indexed_values = []
        for value in values:
            if value in keys:
                index = keys[value]
            else:
                index = counter
                keys[value] = counter
                counter += 1
            indexed_values.append(index)
        return list(keys.keys()), indexed_values

    @staticmethod
    def _expand_values(keys, indexed_values):
        """
        Restore full values from key indices.

        >>> Field._expand_values(['A', 'B'], [0, 0, 1, 0])
        ['A', 'A', 'B', 'A']
        """
        values = [keys[index] for index in indexed_values]
        return values


class Identifier(Field):
    """Class for record identifiers."""

    def __init__(self, field_id, **kwargs):
        """Init Identifier class."""
        super().__init__(field_id, **kwargs)
        self.type = 'identifier'

    def to_set(self):
        """Create a set of identifiers."""
        unique = set()
        for value in self.values:
            unique.add(value)
        return unique

    @staticmethod
    def check_unique(entries):
        """Check all entries are unique."""
        unique = set()
        for entry in entries:
            unique.add(entry)
        return len(unique) == len(entries)

    def validate_list(self, names):
        """Ensure all list entries are unique and match identifiers."""
        valid = True
        if self.check_unique(names):
            if len(self.get_indices_by_values(names)) != len(names):
                valid = False
        else:
            valid = False
        return valid


class Variable(Field):
    """Class for variable field type."""

    def __init__(self, field_id, **kwargs):
        """Init Variable class."""
        super().__init__(field_id, **kwargs)
        self.type = 'variable'

    def get_indices_in_range(self, min_max, invert=False):
        """Get indices for all records in range."""
        if not isinstance(min_max, list):
            return -1
        if not len(min_max) == 2:
            return -2
        if not all(isinstance(x, numbers.Real) for x in min_max):
            return -3
        indices = []
        for index, value in enumerate(self.values):
            if invert:
                if value < min_max[0] or value > min_max[1]:
                    indices.append(index)
            else:
                if min_max[0] <= value <= min_max[1]:
                    indices.append(index)
        return indices

    def sum_values(self):
        """Sum values in subset."""
        try:
            total = reduce(add, self.subset)
        except TypeError:
            total = 0
        return total


class Array(Field):
    """Class for Array field type."""

    def __init__(self, field_id, **kwargs):
        """Init Array class."""
        self.category_slot = None
        if 'category_slot' in kwargs and 'keys' not in kwargs:
            slot = kwargs['category_slot']
            cat_values = [value[slot] for value in kwargs['values']]
            keys = kwargs.get('fixed_keys', [])
            kwargs['keys'], values = self._collapse_values(cat_values, keys)
            for index, value in enumerate(kwargs['values']):
                value[slot] = values[index]
        super().__init__(field_id, **kwargs)
        self.type = 'array'

    def get_values_by_indices_for_slots(self, indices, slots):
        """Get values from specified array slots at matching indices."""
        raw_values = self.get_values_by_indices(indices)
        values = []
        if isinstance(slots, list):
            values = list(map(lambda x: [x[slot] for slot in slots], raw_values))
        else:
            values = list(map(lambda x: x[slots], raw_values))
        return values

    def update_slots(self, values, slot=0, keys=None):
        """Update values in specified slot."""
        if keys is None:
            keys = []
        if len(values) == len(self.values):
            for index, value in enumerate(values):
                self.values[index][slot] = value


class MultiArray(Field):
    """Class for MultiArray field type."""

    def __init__(self, field_id, **kwargs):
        """Init MultiArray class."""
        self.category_slot = None
        if 'category_slot' in kwargs and 'keys' not in kwargs:
            slot = kwargs['category_slot']
            cat_values = []
            for record in kwargs['values']:
                if record:
                    for arr in record:
                        cat_values.append(arr[slot])
            keys = kwargs.get('fixed_keys', [])
            kwargs['keys'], values = self._collapse_values(cat_values, keys)
            index = 0
            for record in kwargs['values']:
                if record:
                    for arr in record:
                        arr[slot] = values[index]
                        index += 1
        super().__init__(field_id, **kwargs)
        self.type = 'array'


class Category(Field):
    """Class for Category field type."""

    def __init__(self, field_id, **kwargs):
        """Init Category class."""
        if 'keys' not in kwargs:
            keys = kwargs.get('fixed_keys', [])
            kwargs['keys'], kwargs['values'] = self._collapse_values(kwargs['values'], keys)
        super().__init__(field_id, **kwargs)
        self.type = 'category'

    def expand_values(self):
        """Return list of full values."""
        return self._expand_values(self.keys, self.values)

    def second_func(self):
        """Do something else."""
        return self.type


__all__ = ['Array', 'Category', 'Field', 'Identifier', 'MultiArray', 'Variable']


if __name__ == '__main__':
    import doctest
    doctest.testmod()