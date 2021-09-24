from asyncio.coroutines import iscoroutinefunction
from typing import Callable, Any, Union, Dict
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
        self.nested_dicts = set()

    def set_max_memory(self, size: IntOrFloat) -> None:
        self.max_memory = size

    def append_nested_dict(self, dictionary: Dict) -> None:
        """
        This method adds any nested MemorySafeDict to a list so it can add it to the total size.
        Not adding your nested dict could make your max memory not effective.
        Don't use this unless you are using the max_memory feature.
        """
        self.nested_dicts.add(dictionary)

    def __missing__(self, key) -> None:
        try:
            self.data[key] = self.default()
            if self.max_memory is not None:
                if self.getsize() >= self.max_memory:
                    raise MemoryError
        except MemoryError:
            self.clear()
            self.data[key] = self.default()

    def __getitem__(self, key) -> Any:
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
                    return self.data[key]
            if self.main.max_memory is not None:
                if self.main.getsize() >= self.main.max_memory:
                    self.clear()
                    self.data[key] = self.default()
        return self.data[key]

    def __setitem__(self, key, value) -> None:
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
             
    def __repr__(self) -> str:
        return str(self.data)

    def __iter__(self):
        for key in self.data:
            yield key

    def __call__(self):
        """
        Calls all callable values in the dict.
        """
        funcs = [value for value in self.data.values() if callable(value) and not iscoroutinefunction(value)]
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

    def any(self) -> bool:
        for value in self.data.values():
            if not value:
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
        self.nested_dicts.clear()

    def sorted_values(self, reverse: bool = False) -> list:
        return self.data.values().sort(reverse=reverse)

    def sorted_keys(self, reverse: bool = False) -> list:
        return self.data.keys().sort(reverse=reverse)

# Tesing performance
import time

def test():
    start = time.time()
    dict = MemorySafeDict(max_memory=1)
    dict[1] = MemorySafeDict(main=dict)
    dict.append_nested_dict(dict[1])
    for i in range(1000000):
        dict[1].update({i:i})
    end = time.time()
    print(end-start)

if __name__ == "__main__":
    test()

