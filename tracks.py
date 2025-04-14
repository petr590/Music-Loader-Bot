import urllib.parse
import requests
import re
import logging

from bs4 import BeautifulSoup, Tag
from typing import List, Dict, Optional, Callable
from abc import abstractmethod

HEADERS = {
	'Accept': 'text/html',
	'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 12_3_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.4 Safari/605.1.15',
}

FORBIDDEN_CHARS = re.compile(r'[\\|/:*?<>"\x00-\x1F]')
HREF_REGEX = re.compile(r'^((https?:)?//)?')

logger = logging.getLogger('root')


class Track:
	__cache: Dict[int, str] = {}

	def __init__(self, url: str, title: str, author: str, duration: str):
		self.url = url
		self.title = title
		self.author = author
		self.duration = duration
		Track.__cache[self.id] = self
	
	@property
	def id(self) -> int:
		return id(self)


	@staticmethod
	def get_cached(id: int) -> Optional['Track']:
		return Track.__cache.get(id)
	
	def get_text(self) -> str:
		return f'{self.author}   ⸺   {self.title}   ⸺   {self.duration}'
	
	def get_filename(self) -> str:
		return re.sub(FORBIDDEN_CHARS, '_', f'{self.author} - {self.title}')


class TrackSource:
	@abstractmethod
	def add_tracks(self, tracks: List[Track], request: str, req_author: Optional[str], req_title: Optional[str]) -> None:
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
	
	def __add_tracks_from_page(self, tracks: List[Track], req_author: Optional[str], req_title: Optional[str], url: str) -> Optional[BeautifulSoup]:
		""" Добавляет совпадающие треки в переданный список. Возвращает страницу. """

		response = requests.get(url, HEADERS)

		if not response.ok:
			logger.warning(f'Server returned code {response.status_code} for GET {url}')
			return None
		
		soup = BeautifulSoup(response.text, 'lxml')

		for tag in soup.find_all(attrs=self.track_attrs):
			href = re.sub(HREF_REGEX, 'https://', tag.find('a', self.link_attrs)['href'])

			title = tag.find(attrs=self.title_attrs).get_text(strip=True)
			if req_title is not None and title.lower().find(req_title.lower()) == -1:
				continue

			author = tag.find(attrs=self.author_attrs).get_text(strip=True)
			if req_author is not None and author.lower().find(req_author.lower()) == -1:
				continue

			time = tag.find(attrs=self.time_attrs).get_text(strip=True)

			tracks.append(Track(href, title, author, time))
		

	def add_tracks(self, tracks: List[Track], request: str, req_author: Optional[str], req_title: Optional[str]):
		url = self.base + urllib.parse.quote(request, safe='')

		soup = self.__add_tracks_from_page(tracks, req_author, req_title, url)
		if soup is None: return

		pagination = soup.find(attrs=self.pagination_attrs)

		if pagination is not None:
			for link in pagination.find_all('a'):
				if self.pagination_link_predicate(link):
					self.__add_tracks_from_page(tracks, req_author, req_title, urllib.parse.urljoin(self.host, link['href']))



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


def load_tracks(request: str, req_author: Optional[str], req_title: Optional[str]) -> List[Track]:
	""" Возвращает список треков по запросу """

	tracks = []
	
	LIGAUDIO_TRACK_SOURCE.add_tracks(tracks, request, req_author, req_title)
	HITMOS_TRACK_SOURCE.add_tracks(tracks, request, req_author, req_title)

	logger.debug(f'Found {len(tracks)} tracks by request `{request}`')
	return tracks