import requests
import tempfile
import os.path
import logging

from mutagen.easyid3 import EasyID3
from pydub import AudioSegment
from pydub.utils import mediainfo
from telebot import TeleBot

from tracks import Track
from util import Timer, HEADERS, add_scheme


TARGET_BITRATE = 192000
TARGET_FORMAT = 'mp3'
MAX_TRIES = 3

logger = logging.getLogger()

def process_track(track: Track, bot: TeleBot, chat_id: int) -> None:
	""" Скачивает трек по ссылке, затем преобразовывает его в формат TARGET_FORMAT,
		сжимает до битрейта TARGET_BITRATE и устанавливает метаданные. """

	message_id = bot.send_message(chat_id, 'Скачиваю файл...').id

	total_timer = Timer()
	total_timer.start()

	timer = Timer()
	timer.start()

	response = requests.get(add_scheme(track.url), headers=HEADERS)

	if not response.ok:
		logger.warning(f'Server returned status {response.status_code} on request {track.url}')
		bot.delete_message(chat_id, message_id)
		bot.send_message(chat_id, 'Ошибка при скачавании файла')
		return
	
	timer.stop('File downloading')

	with tempfile.TemporaryDirectory() as dirname,\
		open(os.path.join(dirname, track.get_filename() + '.' + TARGET_FORMAT), 'w+b') as file:
		timer.run('File writing', lambda: file.write(response.content))

		timer.start()
		info = mediainfo(file.name)
		bitrate = int(info['bit_rate'])
		timer.stop('Mediainfo reading')

		if bitrate > TARGET_BITRATE or info['format_name'] != TARGET_FORMAT:
			audio: AudioSegment = timer.run('File reading', lambda:
					AudioSegment.from_file(file.name))

			timer.run('File processing', lambda:
					audio.export(file.name, TARGET_FORMAT, bitrate=str(min(bitrate, TARGET_BITRATE))))
		

		timer.start()
		id3 = EasyID3(file.name)
		id3.clear()
		id3['title'] = track.title
		id3['artist'] = track.author
		id3.save()
		timer.stop('Metadata writing')


		timer.start()

		for trying in range(MAX_TRIES):
			try:
				file.seek(0)
				bot.send_audio(chat_id, file)
				break
			except requests.exceptions.ConnectionError as error:
				if trying == MAX_TRIES - 1:
					raise error
				else:
					logger.warning('Caugth requests.exceptions.ConnectionError, retrying...')

		timer.stop('Audio sending')
		
		bot.delete_message(chat_id, message_id)
	
	total_timer.stop('Total time')