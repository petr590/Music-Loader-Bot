#!/bin/python3
import os

from musbot import database, file_manager

def main():
	database.init()

	ADMIN_ID = int(os.environ.get('ADMIN_ID'))
	tracks = database.get_track_list(ADMIN_ID, None, None)
 
	for track in tracks:
		file_manager.create_track_symlink(track)


if __name__ == '__main__':
	main()