from abc import abstractmethod
from typing import Dict, Type
from telebot import TeleBot, types

from . import database, file_manager
from .tracks import Track
from .track_processor import send_track

class Action:
	"""
	Действие - абстракция над сообщениями telebot. Каждое действие может вернуть себя
	или другое действие, так организуется "переход" между ними.
	"""

	def __init__(self, track: Track) -> None:
		self.track = track
	
	def filter(self, message: types.Message) -> bool:
		"""
		Возвращает True, если сообщение применимо к действию.
		По умолчанию всегда возвращает True.
		"""
		return True
	
	@abstractmethod
	def handle_message(self, message: types.Message, bot: TeleBot) -> 'Action':
		"""
		Выполняет очередное действие. Возвращает следующее действие
		(возможно, self), если действие не окончено, иначе NO_ACTION.
		"""


class NoAction(Action):
	"""
	Представляет отсутствие действия в данный момент.
	Никогда не обрабатывается, так как метод filter всегда возвращает False.
	Может быть заменено на другое действие только вручную.
	"""

	def __init__(self) -> None:
		super().__init__(None)
	
	@staticmethod
	def getter(track: Track) -> 'NoAction':
		return NO_ACTION
	
	def filter(self, message: types.Message) -> bool:
		return False
	
	def handle_message(self, message: types.Message, bot: TeleBot) -> Action:
		return self


# Единственный экземпляр класса
NO_ACTION = NoAction()

KEYBOARD_REMOVE = types.ReplyKeyboardRemove()

class EditAction(Action):
	def __init__(self, track: Track) -> None:
		super().__init__(track)
		self._second_stage = False
	
	def handle_message(self, message: types.Message, bot: TeleBot) -> Action:
		if not self._second_stage:
			bot.send_message(message.chat.id, self._get_message(), reply_markup=KEYBOARD_REMOVE)
			self._second_stage = True
			return self
		else:
			old_track = self.track.copy()
			self._edit_value(message.text)

			database.update_track(self.track)
			file_manager.update_track(self.track, old_track)

			bot.send_message(message.chat.id, 'Трек изменён')
			return NO_ACTION
	
	@abstractmethod
	def _get_message(self) -> str:
		""" Возвращает сообщение, которое будет отправлено пользователю """
	
	@abstractmethod
	def _edit_value(self, message: str) -> None:
		""" Редактирует self.track """


class EditAuthorAction(EditAction):
	def __init__(self, track: Track) -> None:
		super().__init__(track)
	
	def _get_message(self) -> str:
		return f'Введите нового автора трека. Текущий автор:\n{self.track.author}'
	
	def _edit_value(self, message: str):
		self.track.author = message


class EditTitleAction(EditAction):
	def __init__(self, track: Track) -> None:
		super().__init__(track)
	
	def _get_message(self) -> str:
		return f'Введите новое название трека. Текущее название:\n{self.track.title}'
	
	def _edit_value(self, message: str):
		self.track.title = message


class DownloadTrackAction(Action):
	def __init__(self, track: Track) -> None:
		super().__init__(track)

	def handle_message(self, message: types.Message, bot: TeleBot) -> Action:
		send_track(self.track, bot, message.chat.id)
		return NO_ACTION


class DeleteTrackAction(Action):
	__keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True).add(
		types.KeyboardButton('Да'),
		types.KeyboardButton('Нет'),
	)

	def __init__(self, track: Track) -> None:
		super().__init__(track)
		self._second_stage = False

	def handle_message(self, message: types.Message, bot: TeleBot) -> Action:
		if not self._second_stage:
			bot.send_message(message.chat.id, 'Вы уверены?', reply_markup=DeleteTrackAction.__keyboard)
			self._second_stage = True
			return self
		
		if message.text.lower() == 'да':
			database.delete_track(self.track)
			file_manager.delete_track(self.track)
			bot.send_message(message.chat.id, 'Трек удалён', reply_markup=KEYBOARD_REMOVE)
		else:
			bot.send_message(message.chat.id, 'Отменено', reply_markup=KEYBOARD_REMOVE)

		return NO_ACTION



ACTION_BY_BUTTON_MESSAGE: Dict[str, Type[Action]] = {
	'Изменить автора':   EditAuthorAction,
	'Изменить название': EditTitleAction,
	'Скачать':           DownloadTrackAction,
	'Удалить':           DeleteTrackAction,
}


class ChooseAction(Action):
	def __init__(self, track: Track) -> None:
		super().__init__(track)
	
	def filter(self, message: types.Message) -> bool:
		return message.text in ACTION_BY_BUTTON_MESSAGE
	
	def handle_message(self, message: types.Message, bot: TeleBot) -> Action:
		return ACTION_BY_BUTTON_MESSAGE.get(message.text, NoAction.getter)(self.track)\
			.handle_message(message, bot)


class SetAction(Action):
	def __init__(self, track: Track) -> None:
		super().__init__(track)
	
	def handle_message(self, message: types.Message, bot: TeleBot) -> Action:
		self._edit(message.text)
		return NO_ACTION
	
	@abstractmethod
	def _edit(self, message: str) -> None:
		""" Редактирует self.track """

class SetAuthorAction(SetAction):
	def __init__(self, track: Track) -> None:
		super().__init__(track)
	
	def _edit(self, message: str) -> None:
		self.track.author = message

class SetTitleAction(SetAction):
	def __init__(self, track: Track) -> None:
		super().__init__(track)
	
	def _edit(self, message: str) -> None:
		self.track.title = message
