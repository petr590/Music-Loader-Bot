import time
import logging
from typing import Callable, TypeVar

logger = logging.getLogger('root')
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

		logger.debug(f'{message}: {end - self.__start} sec')
		self.__start = None
	
	def run(self, message: str, func: Callable[[], T]) -> T:
		self.start()
		result = func()
		self.stop(message)
		return result


def word_form_by_num(num: int, word_1: str, word_2_4: str, word_many: str) -> str:
	ones = num % 10
	tens = num % 100 // 10

	if tens == 1: return word_many
	if ones == 1: return word_1
	if 2 <= ones <= 4: return word_2_4
	return word_many