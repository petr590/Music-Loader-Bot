import os
import psycopg2
import logging

from telebot.types import User
from typing import List, Dict, Optional

from .tracks import Track, TrackPool

logger = logging.getLogger('root')

def init() -> None:
	global connection, cursor
	
	connection = psycopg2.connect(
		dbname   = os.environ.get('DB_NAME'),
		host     = os.environ.get('DB_HOST'),
		port     = os.environ.get('DB_PORT'),
		user     = os.environ.get('DB_USER'),
		password = os.environ.get('DB_PASSWORD')
	)

	cursor = connection.cursor()

	# Основные таблицы
	cursor.execute("""CREATE TABLE IF NOT EXISTS users (
					id BIGINT PRIMARY KEY,
					name VARCHAR(65536) NOT NULL
			   )""")

	cursor.execute("""CREATE TABLE IF NOT EXISTS tracks (
						id SERIAL PRIMARY KEY,
						user_id BIGINT NOT NULL REFERENCES users(id),
						url VARCHAR(2048) NOT NULL,
						title VARCHAR(2048) NOT NULL,
						author VARCHAR(2048) NOT NULL,
						duration SMALLINT NOT NULL,
						UNIQUE(user_id, url)
					)""")

	# Таблицы для сериализации
	cursor.execute("""CREATE TABLE IF NOT EXISTS saved_track_pools (
						id SERIAL PRIMARY KEY,
						user_id BIGINT NOT NULL REFERENCES users(id),
						message_id BIGINT NOT NULL,
						page INT NOT NULL,
						callback VARCHAR(100) NOT NULL
					)""")
	
	cursor.execute("""CREATE TABLE IF NOT EXISTS saved_tracks (
						url VARCHAR(2048) NOT NULL,
						title VARCHAR(2048) NOT NULL,
						author VARCHAR(2048) NOT NULL,
						duration SMALLINT NOT NULL,
						saved_id BIGINT REFERENCES tracks(id) ON DELETE SET NULL,
						keynum INT NOT NULL,
						track_pool_id BIGINT NOT NULL REFERENCES saved_track_pools(id)
					)""")
	
 	# Для ускорения ON DELETE SET NULL
	cursor.execute("CREATE INDEX IF NOT EXISTS saved_tracks_saved_id_idx ON saved_tracks(saved_id)")
	
	connection.commit()


def cleanup() -> None:
	cursor.close()
	connection.close()


def add_or_update_user(user: User) -> None:
	cursor.execute("""INSERT INTO users (id, name) VALUES (%s, %s)
					  ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name""",
				   (user.id, user.username))
	
	connection.commit()


def add_or_update_track(user_id: int, track: Track) -> int:
	cursor.execute("""INSERT INTO tracks (user_id, url, title, author, duration)
					  VALUES (%s, %s, %s, %s, %s)
					  ON CONFLICT (user_id, url)
					  DO UPDATE SET title=EXCLUDED.title, author=EXCLUDED.author, duration=EXCLUDED.duration
       				  RETURNING id""",
				   (user_id, track.url, track.title, track.author, track.duration))
	
	connection.commit()
	return cursor.fetchone()[0]


def _escape_like_pattern(string: str) -> str:
	return '%' + string.replace('=', '==').replace('%', '=%').replace('_', '=_') + '%'


def get_track_list(user_id: int, title: Optional[str], author: Optional[str]) -> List[Track]:
	query = "SELECT id, url, title, author, duration FROM tracks WHERE user_id = %s"
	args = [user_id]
	
	if title is not None:
		query += " AND title ILIKE %s ESCAPE '='"
		args.append(_escape_like_pattern(title))
	
	if author is not None:
		query += " AND author ILIKE %s ESCAPE '='"
		args.append(_escape_like_pattern(author))
	
	query += " ORDER BY author, title DESC"
	
	cursor.execute(query, args)
	connection.commit()
	
	tracks = list(map(
		lambda row: Track(id=row[0], url=row[1], title=row[2], author=row[3], duration=row[4]),
		cursor
	))

	tracks.sort()
	return tracks


def update_track(track: Track) -> None:
	cursor.execute("UPDATE tracks SET url=%s, title=%s, author=%s, duration=%s WHERE id=%s",
				   (track.url, track.title, track.author, track.duration, track.id))

	connection.commit()


def delete_track(track: Track) -> None:
	cursor.execute("DELETE FROM tracks WHERE id=%s", (track.id,))
	connection.commit()


def set_ids(user_id: int, tracks: List[Track]) -> None:
	""" Для каждого трека устанавливает id, если трек есть в базе """

	if len(tracks) == 0: return

	urls = tuple(track.url for track in tracks)
 
	cursor.execute("SELECT id, url FROM tracks WHERE user_id=%s AND url IN %s", (user_id, urls))
	connection.commit()
	
	found_urls = { row[1]: row[0] for row in cursor }
	for track in tracks:
		track.id = found_urls.get(track.url, None)


def _mogrify_saved_track(track: Track, pool: TrackPool) -> str:
    return cursor.mogrify(
			"(%s,%s,%s,%s,%s,%s,%s)",
			(track.url, track.title, track.author, track.duration, track.id, track.keynum, pool.id)
		).decode('utf-8')


def serialize_track_pools(track_pools: Dict[int, TrackPool]) -> None:
	cursor.execute("DELETE FROM saved_tracks")
	cursor.execute("DELETE FROM saved_track_pools")
	connection.commit()
 

	args = b",".join(cursor.mogrify(
     		"(%s,%s,%s,%s,%s)",
			(pool.id, pool.user_id, pool.message_id, pool.page, pool.callback.__name__)
		) for pool in track_pools.values())
	
	if len(args) > 0:
		cursor.execute(b"INSERT INTO saved_track_pools (id, user_id, message_id, page, callback) VALUES " + args)

	
	args = ",".join(_mogrify_saved_track(track, pool) for pool in track_pools.values() for track in pool.tracks)
 
	if len(args) > 0:
		fields = '(url, title, author, duration, saved_id, keynum, track_pool_id)'
		
		cursor.execute(f"""
			INSERT INTO saved_tracks {fields}
				SELECT tmp.url, tmp.title, tmp.author, tmp.duration,
    					CASE WHEN tracks.id IS NULL THEN NULL ELSE tmp.saved_id END,
         				tmp.keynum, tmp.track_pool_id
				FROM (VALUES {args}) AS tmp {fields}
				LEFT JOIN tracks ON saved_id=tracks.id
    	""")
    
	track_count = sum(1 for pool in track_pools.values() for track in pool.tracks)
	logger.debug(f'Saved {len(track_pools)} track pools and {track_count} tracks')

	connection.commit()


def deserialize_track_pools(callbacks: list) -> Dict[int, TrackPool]:
	callbacks_dict = { callback.__name__: callback for callback in callbacks }
 
	cursor.execute("SELECT id, user_id, message_id, page, callback FROM saved_track_pools")
	connection.commit()
 
	track_pools: Dict[int, TrackPool] = {}

	for row in cursor:
		track_pools[row[0]] = TrackPool(id=row[0], user_id=row[1], message_id=row[2], page=row[3], callback=callbacks_dict[row[4]])


	cursor.execute("SELECT url, title, author, duration, saved_id, keynum, track_pool_id FROM saved_tracks")
	connection.commit()
 
	track_count = 0

	for row in cursor:
		track = Track(row[0], row[1], row[2], row[3], row[4], row[5])
		track_pools[row[6]].add_track(track)
		track_count += 1

	logger.debug(f'Loaded {len(track_pools)} track pools and {track_count} tracks')
	return track_pools
