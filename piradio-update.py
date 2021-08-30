import json
import re
import os.path
import wget
from datetime import datetime
from pydub import AudioSegment



from listennotes import podcast_api
from gtts import gTTS 

api_key='' # set API to nothing to use the ListenNotes test API stubs
api_key = os.environ.get('LISTENNOTES_API_KEY')
root_folder="podcasts"

            
def clean_folder_name(s):
	s=s.lower();
	s=re.sub(r'[^a-z0-9]+','-', s)
	s=re.sub(r'^-','', s) #remove any leading "-" as it messes up globbing
	return s


client = podcast_api.Client(api_key=api_key)

response = client.fetch_playlist_by_id(id=os.environ.get('LISTENNOTES_PLAYLIST_ID'), type='podcast_list', sort='recent_published_first')
podcast_list=response.json()

for podcast in podcast_list['items']:
	title=podcast['data']['title']
	title_fn=root_folder+"/"+clean_folder_name(title)

	if(not os.path.exists(title_fn) ):
		#create podcast folder
		os.mkdir(title_fn)

	if(not os.path.isfile(title_fn+"/podcast_title.mp3")):
		# create MP3 of spoken title
		speech = gTTS(text = title, lang = "en", slow = False)
		speech.save(title_fn+"/podcast_title.mp3")

	#convert spoken title to WAV format for speed of loading
	sound = AudioSegment.from_mp3(title_fn+"/podcast_title.mp3")
	sound.export(title_fn+"/podcast_title.wav", format="wav")

	#get last episode download date
	last_download_date=None
	try:
		with open(title_fn+"/last_download.txt", 'r') as f:
			last_download_date=f.read()
		if(re.match(r"/d/d/d/d-/d/d-/d/d",last_download_date)):
			last_download_date=int(datetime.strptime(last_download_date, "%Y-%m-%d").timestamp()*1000)
	except:
		pass

	episodes_downloaded=0
	while(not episodes_downloaded):
		podcast_id=podcast['data']['id']
		response = client.fetch_podcast_by_id(id=podcast_id, sort="oldest_first", next_episode_pub_date=last_download_date)
		episode_list=response.json()

		if(len(episode_list["episodes"])>0):
			for episode in episode_list["episodes"]:
				episode_title=episode['title']
				episode_title_fn=title_fn+"/"+clean_folder_name(episode_title)
				if(not os.path.exists(episode_title_fn)):
					os.mkdir(episode_title_fn)

				# download audio file
				if(os.path.isfile(episode_title_fn+"/episode_listened.txt") and os.path.isfile(episode_title_fn+"/episode_audio.mp3")):
					print("deleting listened podcast episode {}".format(episode_title_fn))
					os.remove(episode_title_fn+"/episode_audio.mp3")
				if(not os.path.isfile(episode_title_fn+"/episode_listened.txt") and not os.path.isfile(episode_title_fn+"/episode_audio.mp3")):
					print("downloading podcast episode {}".format(episode_title_fn))
					try:
						wget.download(episode['audio'], episode_title_fn+"/episode_audio.mp3")
						last_download_date=episode_list['next_episode_pub_date']
						episodes_downloaded+=1
					except:
						pass

				# generate the speech of the title
				if(not os.path.isfile(episode_title_fn+"/episode_title.mp3")):
					speech=gTTS(text = episode_title, lang="en", slow=False)
					speech.save(episode_title_fn+"/"+"episode_title.mp3")
					sound = AudioSegment.from_mp3(episode_title_fn+"/episode_title.mp3")
					sound.export(episode_title_fn+"/episode_title.wav", format="wav")

				# set published date indicators
				pub_date_s=int(episode['pub_date_ms']/1000) # utime expects seconds
				pub_date_f = open(episode_title_fn+"/pub_date.txt", "w")
				print(" published on {}".format(datetime.utcfromtimestamp(pub_date_s).strftime('%Y-%m-%d')))
				pub_date_f.write(datetime.utcfromtimestamp(pub_date_s).strftime('%Y-%m-%d'))
				pub_date_f.close()
				os.utime(episode_title_fn+"/pub_date.txt",(pub_date_s,pub_date_s))			
				os.utime(episode_title_fn, (pub_date_s,pub_date_s)) 

			if(episodes_downloaded < len(episode_list["episodes"]) ):
				last_download_date=episode_list["next_episode_pub_date"]

		else:
			break # no episode available for this podcast - leave it and move on

	# done getting episodes, so update the podcast download date
	if(episodes_downloaded>0):
		print("downloaded {} episodes of {}".format(episodes_downloaded, title_fn))
		with open(title_fn+"/last_download.txt", 'w') as f:
			f.write(str(last_download_date))
