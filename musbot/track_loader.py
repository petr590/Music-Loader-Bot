import urllib.parse
import requests
import logging
import re

from bs4 import BeautifulSoup, Tag
from typing import List, Dict, Optional, Callable
from abc import abstractmethod

from .tracks import Track
from .util import HEADERS, remove_scheme

# Удаляет '//', 'http://' и 'https://' в начале строки, если есть, и добавляет 'https://'
HREF_REGEX = re.compile(r'^((https?:)?//)?')
HREF_REPL = 'https://'

# Ищет время в строке
TIME_GROUP = r'([0-5]?\d)'
TIME_REGEX = re.compile(f'^{TIME_GROUP}:{TIME_GROUP}(?::{TIME_GROUP})?$')

WHITESPACE_REGEX = re.compile(r'\s+')

logger = logging.getLogger('root')


def _matches(value: str, required: Optional[str]) -> bool:
	"""
	Проверяет, что val соответствует тому, что указано в req_val.
	Если req_val равен None, то возвращает True
	"""

	if required is None:
		return True

	value = value.lower()
	required = required.lower()

	reqs = re.split(WHITESPACE_REGEX, required)
	return all(value.find(req) != -1 for req in reqs)


class TrackSource:
	@abstractmethod
	def add_tracks(self, tracks: List[Track], request: str, req_title: Optional[str], req_author: Optional[str]) -> None:
		""" Добавляет треки в итоговый список """


Attrs = Dict[str, str]

class SimpleTrackSource(TrackSource):
	def __init__(self, host: str, base: str,
				 track_attrs: Attrs, link_attrs: Attrs, title_attrs: Attrs,
				 author_attrs: Attrs, time_attrs: Attrs, pagination_attrs: Attrs,
				 pagination_link_predicate: Callable[[Tag], bool]) -> None:
		
		self.host = host
		self.base = base
		self.track_attrs      = track_attrs
		self.link_attrs       = link_attrs
		self.title_attrs      = title_attrs
		self.author_attrs     = author_attrs
		self.time_attrs       = time_attrs
		self.pagination_attrs = pagination_attrs
		self.pagination_link_predicate = pagination_link_predicate
	
	def __add_tracks_from_page(self, tracks: List[Track], req_title: Optional[str], req_author: Optional[str], url: str) -> Optional[BeautifulSoup]:
		""" Добавляет совпадающие треки в переданный список. Возвращает страницу. """

		response = requests.get(url, HEADERS)

		if not response.ok:
			logger.warning(f'Server returned code {response.status_code} for GET {url}')
			return None
		
		soup = BeautifulSoup(response.text, 'lxml')

		for tag in soup.find_all(attrs=self.track_attrs):
			href = re.sub(HREF_REGEX, HREF_REPL, tag.find('a', self.link_attrs)['href'])

			title = tag.find(attrs=self.title_attrs).get_text(strip=True)
			if not _matches(title, req_title):
				continue

			author = tag.find(attrs=self.author_attrs).get_text(strip=True)
			if not _matches(author, req_author):
				continue

			match = re.search(TIME_REGEX, tag.find(attrs=self.time_attrs).get_text(strip=True))

			if match is not None:
				time = int(match.group(1)) * 60 + int(match.group(2))

				if match.group(3):
					time = time * 60 + int(match.group(3))
			else:
				time = -1

			tracks.append(Track(remove_scheme(href), title, author, time))


	def add_tracks(self, tracks: List[Track], request: str, req_title: Optional[str], req_author: Optional[str]):
		url = self.base + urllib.parse.quote(request, safe='')

		soup = self.__add_tracks_from_page(tracks, req_title, req_author, url)
		if soup is None: return

		pagination = soup.find(attrs=self.pagination_attrs)

		if pagination is not None:
			for link in pagination.find_all('a'):
				if self.pagination_link_predicate(link):
					self.__add_tracks_from_page(tracks, req_title, req_author, urllib.parse.urljoin(self.host, link['href']))



LIGAUDIO_TRACK_SOURCE = SimpleTrackSource(
	'https://web.ligaudio.ru',
	'https://web.ligaudio.ru/mp3/',
	{'itemprop': 'track'},
	{'itemprop': 'url'},
	{'class': 'title', 'itemprop': 'name'},
	{'class': 'autor', 'itemprop': 'byArtist'},
	{'class': 'd'},
	{'class': 'pagination'},
	lambda link: 'this' not in link.get_attribute_list('class')
)

HITMOS_TRACK_SOURCE = SimpleTrackSource(
	'https://rus.hitmotop.com',
	'https://rus.hitmotop.com/search?q=',
	{'class': 'track__info'},
	{'class': 'track__download-btn'},
	{'class': 'track__title'},
	{'class': 'track__desc'},
	{'class': 'track__time'},
	{'class': 'pagination'},
	lambda _: True
)


AUTHORS = [
	'9Lana',
	'Ado',
	'Alan Walker',
	'Alba Sera',
	'Amala feat. Hatsune Miku, Kasane Teto',
	'Chiyo',
	'DECO*27 feat. Hatsune Miku',
	'Futakuchi Mana',
	'GUMI',
	'Harmony Team',
	'HaruWei',
	'Hatsune Miku',
	'Kasane Teto',
	'Megurine Luka',
	'higanbanban',
	'Narea',
	'Hiiragi Magnetite',
	'Hinomori Shizuku',
	'Jackie-O & Sati Akura',
	'Jinja',
	'Kagamine Rin',
	'Kusuriya no Hitorigoto',
	'[Labor of Love] Hoski',
	'LIQ feat. Hatsune Miku',
	'LiuVerdea',
	'May\'n',
	'Megurine Luka',
	'Melody Note',
	'Miku',
	'Neoni',
	'Noisia',
	'Onsa Media',
	'Planya Ch',
	'Reoni, Nyami',
	'Sati Akura',
	'SAWTOWNE',
	'SE[L] EI',
	'Utsu-P',
	'Vocaloid',
	'WEDNESDAY CAMPANELLA',
	'Yuyoyuppe',
	'Zephyrianna',
	'ZHIEND',
	'ZUTOMAYO',
	'Ёлка',
	'Amala',
]

AUTHOR_NORM_TABLE = [
	(re.compile(rf'\b{re.escape(author)}\b'), author) for author in AUTHORS
]

AUTHOR_NORM_TABLE.extend([
	(re.compile(r'\b黒うさp\b'), 'Kurousa-P'),
	(re.compile(r'\bplanya channel\b'), 'Planya Ch'),
])

FEAT_REGEX = re.compile(r'(\w) (?: feat|ft)\. (\w)', re.X)
FEAT_REPL = r'\1 feat. \2'

SEPARATOR_REGEX = re.compile(r'(\w) (?: \s*[,&]\s* | \s+x\s+) (\w)', re.X)
SEPARATOR_REPL = r'\1, \2'

def _normalize(track: Track) -> None:
	author = track.author
	author = re.sub(FEAT_REGEX, FEAT_REPL, author)
	author = re.sub(SEPARATOR_REGEX, SEPARATOR_REPL, author)
	
	for entry in AUTHOR_NORM_TABLE:
		author = re.sub(entry[0], entry[1], author)
	
	track.author = author
            


def load_tracks(request: str, req_title: Optional[str], req_author: Optional[str]) -> List[Track]:
	""" Возвращает список треков по запросу """
	tracks = []
	
	LIGAUDIO_TRACK_SOURCE.add_tracks(tracks, request, req_title, req_author)
	HITMOS_TRACK_SOURCE.add_tracks(tracks, request, req_title, req_author)
 
	for track in tracks:
		_normalize(track)
	
	tracks.sort()

	logger.debug(f'Found {len(tracks)} tracks by request `{request}`')
	return tracks