from asyncio.coroutines import iscoroutinefunction
from typing import Callable, Any, Union, Dict, Optional
from asyncio import iscoroutinefunction
from sys import getsizeof
from cpython cimport bool


none = lambda: None


cdef class MemorySafeDict:
    cdef MemorySafeDict main
    max_memory: Optional[int]
    cdef dict data
    cdef list nested_dicts
    default: Callable

    def  __cinit__(self, dict dictionary = None, default = None, max_memory = None, MemorySafeDict main = None):
        self.main = main
        self.max_memory = max_memory * 1024**3 if max_memory is not None else None
        self.default = default or none
        self.data = dictionary or {}
        self.nested_dicts = []

    def set_max_memory(self, int size):
        self.max_memory = size

    def append_nested_dict(self, MemorySafeDict dictionary):
        self.nested_dicts.append(dictionary)

    def __missing__(self, key):
        try:
            self.data[key] = self.default()
            if self.max_memory is not None:
                if self.getsize() >= self.max_memory:
                    raise MemoryError
        except MemoryError:
            self.clear()
            self.data[key] = self.default()

    def __getitem__(self, key):
        if key not in self.data:
            try:
                self.data[key] = self.default()
                if self.max_memory is not None:
                    if self.getsize() >= self.max_memory:
                        raise MemoryError
            except MemoryError:
                self.clear()
                self.data[key] = self.default()

            if self.main is None:
                    return
            if self.main.max_memory is not None:
                if self.main.getsize() >= self.main.max_memory:
                    self.clear()
                    self.data[key] = self.default()
        return self.data[key]

    def __setitem__(self, key, value):
        try:
            if self.max_memory is not None and key not in self.data:
                if self.getsize() >= self.max_memory:
                    raise MemoryError
            self.data[key] = value
        except MemoryError:
            self.clear()
            self.data[key] = value
        finally:
            if self.main is None:
                return
            if self.main.max_memory is not None:
                if self.main.getsize() >= self.main.max_memory:
                    self.clear()
                    self.data[key] = value
             
    def __repr__(self):
        return str(self.data)

    def __iter__(self):
        for key in self.data:
            yield key

    def __call__(self):
        cdef list funcs = [value for value in self.data.values() if callable(value) and not iscoroutinefunction(value)]
        for func in funcs:
            func()
    
    def __delitem__(self, key):
        del self.data[key]

    def __len__(self):
        counter = 0
        for _ in self.data:
            counter += 1
        return counter

    def pop(self, key):
        self.data.pop(key)

    def keys(self):
       return [key for key in self.data]

    def values(self):
        return [self.data[key] for key in self.data]

    def update(self, dict dictionary):
        try:
            for key in dictionary:
                if self.max_memory is not None and key not in self.data:
                    if self.getsize() >= self.max_memory:
                        raise MemoryError
                self.data[key] = dictionary[key]
        except MemoryError:
            self.clear()
            for key in dictionary:
                self.data[key] = dictionary[key]
        finally:
            if self.main is None:
                return
            if self.main.max_memory is not None:
                if self.main.getsize() >= self.main.max_memory:
                    self.clear()
                    for key in dictionary:
                        self.data[key] = dictionary[key]

    def any(self):
        for value in self.data.values():
            if not value:
                return False
        return True

    def getsize(self):
        cdef int size, nested_dict_size
        size = getsizeof(self.data)
        if len(self.nested_dicts) > 0:
            nested_dict_size = sum(item.getsize() for item in self.nested_dicts)
            return size + nested_dict_size
        return size

    def get(self, key):
        if key not in self.data:
            return None
        return self.data[key]

    def clear(self):
        self.data.clear()
        self.nested_dicts.clear()

    def sorted_values(self, bool reverse = False):
        return self.data.values().sort(reverse=reverse)

    def sorted_keys(self, bool reverse = False):
        return self.data.keys().sort(reverse=reverse)