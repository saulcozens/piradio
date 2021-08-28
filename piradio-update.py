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
		os.mkdir(title_fn)
	if(not os.path.isfile(title_fn+"/podcast_title.mp3")):
		speech = gTTS(text = title, lang = "en", slow = False)
		speech.save(title_fn+"/podcast_title.mp3")
	sound = AudioSegment.from_mp3(title_fn+"/podcast_title.mp3")
	sound.export(title_fn+"/podcast_title.wav", format="wav")


	podcast_id=podcast['data']['id']
	response = client.fetch_podcast_by_id(id=podcast_id)
	episode_list=response.json()

	for episode in episode_list["episodes"]:
		episode_title=episode['title']
		episode_title_fn=title_fn+"/"+clean_folder_name(episode_title)
		print(episode_title_fn)
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
		pub_date_f.write(datetime.utcfromtimestamp(pub_date_s).strftime('%Y-%m-%d'))
		pub_date_f.close()
		os.utime(episode_title_fn+"/pub_date.txt",(pub_date_s,pub_date_s))			
		os.utime(episode_title_fn, (pub_date_s,pub_date_s)) 



