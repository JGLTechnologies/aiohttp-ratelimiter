from asyncio.coroutines import iscoroutinefunction
from typing import Callable, Any, Union
from asyncio import iscoroutinefunction
from sys import getsizeof


none = lambda: None


class MemorySafeDict:
    def __init__(self, default: Callable = None, max_memory: Union[int, float] = None) -> None:
        """
        MemorySafeDict acts as a defaultdict, but it allows you to specify the max ammount of memory it can use and it will never throw a MemoryError
        """
        self.max_memory = max_memory
        self.default = default or none
        self.data = dict()

    def __missing__(self, key) -> None:
        try:
            self.data[key] = self.default()
            if self.max_memory is not None:
                if self.getsize() > self.max_memory:
                    raise MemoryError
        except MemoryError:
            self.data.clear()
            self.data[key] = self.default()

    def __getitem__(self, key) -> Any:
        if key not in self.data:
            try:
                self.data[key] = self.default()
                if self.max_memory is not None:
                    if self.getsize() > self.max_memory:
                        raise MemoryError
            except MemoryError:
                self.data.clear()
                self.data[key] = self.default()
        return self.data[key]

    def __setitem__(self, key, value) -> None:
        try:
            self.data[key] = value
            if self.max_memory is not None and key not in self.data:
                if self.getsize() > self.max_memory:
                    raise MemoryError
        except MemoryError:
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
                self.data[key] = dictionary[key]
                if self.max_memory is not None and key not in self.data:
                    if self.getsize() > self.max_memory:
                        raise MemoryError
        except MemoryError:
            self.data.clear()
            for key in dictionary:
                self.data[key] = dictionary[key]

    def any(self) -> bool:
        for key in self.data:
            if not self.data[key]:
                return False
        return True

    def getsize(self) -> float:
        return round(getsizeof(self.data) / 1024**3, 20)

    def get(self, key) -> None:
        if key not in self.data:
            return None
        return self.data[key]

    def clear(self) -> None:
        self.data.clear()