from asyncio.coroutines import iscoroutinefunction
from collections import defaultdict
from typing import Callable, Any, Union
from asyncio import iscoroutinefunction
from sys import getsizeof


none = lambda: None
IntOrFloat = Union[int, float]


class MemorySafeDict:
    def __init__(self, dictionary: dict = None, default: Callable = None, max_memory: IntOrFloat = None, main = None) -> None:
        """
        MemorySafeDict acts as a defaultdict, but it allows you to specify the max ammount of memory it can use and it will never throw a MemoryError
        """
        self.main: MemorySafeDict = main
        self.max_memory = max_memory * 1024**3 if max_memory is not None else None
        self.default = default or none
        self.data = dictionary or {}
        self.nested_dicts = list()

    def set_max_memory(self, size: IntOrFloat):
        self.max_memory = size

    def append_nested_iterable(self, dictionary: dict) -> None:
        self.nested_dicts.append(dictionary)


    def __missing__(self, key) -> None:
        try:
            self.data[key] = self.default()
            if self.max_memory is not None:
                if self.getsize() >= self.max_memory or self.getsize() >= self.main.max_memory:
                    raise MemoryError
        except MemoryError:
            self.data.clear()
            self.data[key] = self.default()

    def __getitem__(self, key) -> Any:
        if key not in self.data:
            try:
                self.data[key] = self.default()
                if self.max_memory is not None:
                    if self.getsize() >= self.max_memory:
                        raise MemoryError
            except MemoryError:
                self.data.clear()
                self.data[key] = self.default()

            if self.main is None:
                    return
            if self.main.max_memory is not None:
                if self.main.getsize() >= self.main.max_memory or self.getsize() >= self.main.max_memory:
                    self.data.clear()
                    self.data[key] = self.default()
        return self.data[key]

    def __setitem__(self, key, value) -> None:
        try:
            if self.max_memory is not None and key not in self.data:
                if self.getsize() >= self.max_memory:
                    raise MemoryError
            self.data[key] = value
        except MemoryError:
            self.data.clear()
            self.data[key] = value
        finally:
            if self.main is None:
                return
            if self.main.max_memory is not None:
                if self.main.getsize() >= self.main.max_memory or self.getsize() >= self.main.max_memory:
                    self.data.clear()
                    self.data[key] = value
             
    def __repr__(self) -> str:
        return str(self.data)

    def __iter__(self):
        for key in self.data:
            yield key

    def __call__(self):
        funcs = [self.data[key] for key in self.data if callable(self.data[key]) and not iscoroutinefunction(self.data[key])]
        for func in funcs:
            func()
    
    def __delitem__(self, key) -> None:
        del self.data[key]

    def __len__(self) -> int:
        counter = 0
        for _ in self.data:
            counter += 1
        return counter

    def pop(self, key) -> None:
        self.data.pop(key)

    def keys(self):
       return [key for key in self.data]

    def values(self):
        return [self.data[key] for key in self.data]

    def update(self, dictionary: dict) -> None:
        try:
            for key in dictionary:
                if self.max_memory is not None and key not in self.data:
                    if self.getsize() >= self.max_memory:
                        raise MemoryError
                self.data[key] = dictionary[key]
        except MemoryError:
            self.data.clear()
            for key in dictionary:
                self.data[key] = dictionary[key]
        finally:
            if self.main is None:
                return
            if self.main.max_memory is not None:
                if self.main.getsize() >= self.main.max_memory or self.getsize() >= self.main.max_memory:
                    self.data.clear()
                    for key in dictionary:
                        self.data[key] = dictionary[key]

    def any(self) -> bool:
        for key in self.data:
            if not self.data[key]:
                return False
        return True

    def getsize(self) -> IntOrFloat:
        size = getsizeof(self.data)
        if len(self.nested_dicts) > 0:
            nested_dict_size = sum(item.getsize() for item in self.nested_dicts)
            return size + nested_dict_size
        return size

    def get(self, key) -> None:
        if key not in self.data:
            return None
        return self.data[key]

    def clear(self) -> None:
        self.data.clear()

# Tesing performance
import time
start = time.time()
dict = MemorySafeDict(max_memory=.5)
dict[1] = MemorySafeDict(main=dict)
dict.append_nested_iterable(dict[1])
for i in range(10000000**100):
    dict[1][i] = i
end = time.time()
print(end-start)

