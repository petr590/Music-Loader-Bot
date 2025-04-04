import time
from typing import Callable, TypeVar

T = TypeVar('T')

class Timer:
	def __init__(self) -> None:
		self.__start = None
	
	def start(self) -> 'Timer':
		self.__start = time.time()
		return self
	
	def stop(self, message: str) -> None:
		end = time.time()

		if self.__start is None:
			raise ValueError('Timer is not started')

		print(f'{message}: {end - self.__start} sec')
		self.__start = None
	
	def run(self, message: str, func: Callable[[], T]) -> T:
		self.start()
		result = func()
		self.stop(message)
		return result