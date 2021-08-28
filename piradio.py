import os
import sys
import time
import re
import pexpect
from pydub import AudioSegment
from pydub.playback import _play_with_simpleaudio
from gpiozero import RotaryEncoder, Button
import board
import neopixel

from pprint import pprint

class AnimationQ:
	current_animation=None
	default_animation=None

	def __init__(self, period):
		self.animation_q=[]
		self.period=period/1000
		self.last_tick=time.time()

	def add_animation(self, animator, param_list):
		self.animation_q.append((animator, param_list))

	def set_default_animation(self, animator, param_list):
		self.default_animation=(animator, param_list)
		pprint(animator)
		pprint(param_list)

	def tick(self):
		now = time.time()

		if(self.last_tick + self.period > now):
			return

		self.last_tick = now

		if(self.current_animation):
			current_animator=self.current_animation[0]
			current_params=self.current_animation[1:]
			if(not current_animator.tick(*current_params)): #current animation is now finished
				if(self.animation_q):
					self.current_animation=self.animation_q.pop(0)
				else:
					self.current_animation=None
					default_animator=self.default_animation[0]
					default_animator.reset()

		else: #there is no animation running
			if(self.animation_q): # but we have one in the queue
				self.current_animation=self.animation_q.pop(0)
				# it will start on the next tick

			if(self.default_animation):
				default_animator=self.default_animation[0]
				default_params=self.default_animation[1:]
				default_animator.tick(*default_params)

class Animator:

	def __init__(self, neo):
		self.neo=neo
		self.reset()

	def reset(self):
		pass

	def tick(self, params):
		return False

class FfwdRwndAnimator(Animator):
	i=0

	def reset(self):
		self.i=0

	def tick(self, params):
		# param must be
		#	colour:		tuple of (R,G,B) each 0-255
		#	direction: 	-1 or +1 for right or left
		#	pixels_on:	int of how many pixels will be lit up 
		(colour,direction,pixels_on)=params

		pixel_spacing=self.neo.n//pixels_on
		self.neo.fill((0,0,0))
		for j in range(int(pixels_on)):
			if(direction>0):
				self.neo[(j*pixel_spacing) + self.i]=colour
			else:
				self.neo[((j+1)*pixel_spacing) - self.i - 1]=colour

		self.neo.show()
		self.i+=1
		if(self.i >= pixel_spacing):
			self.i=0
			return False

		return True

class GlowToColour(Animator):
	i=0

	def reset(self):
		self.i=0

	def tick(self, params):
		# params must be
		#	colour:	tuple of (R,G,B) each 0-255
		#	steps:	number of ticks to get to the colour

		if(len(params)==2):
			(colour, steps)=params
		else:
			pprint(params)
		for j in range(self.neo.n):
			current_c=self.neo[j]
			new_c=(current_c[0]+(((colour[0]-current_c[0])/steps)*self.i), \
				   current_c[1]+(((colour[1]-current_c[1])/steps)*self.i), \
				   current_c[2]+(((colour[2]-current_c[2])/steps)*self.i))
			self.neo[j]=new_c
		self.neo.show()
		self.i+=1
		if(self.i > steps):
			self.i = steps # stays bright until reset
			return False
		return True

class FlashColour(Animator):
	i=0

	def reset(self):
		pass

	def tick(self, params):
		# params must be
		#	colour:	tuple of (R,G,B) each 0-255
		#	ticks_on:	number of ticks to be on
		#	ticks_off:	number of ticks to be off
		(colour, ticks_on, ticks_off)=params
		if(self.i<ticks_on):
			self.neo.fill(colour)
			self.neo.show()
		else:
			self.neo.fill((0,0,0))
			self.neo.show()
		self.i+=1
		if(self.i>ticks_on+ticks_off):
			self.i=0
			return False # the animation is complete
		return True	



class Menu:
	def __init__(self, menu, next_cb=None, prev_cb=None, action_1_cb=None, action_2_cb=None, index=0):
		self.menu=menu
		self.next_cb=next_cb
		self.prev_cb=prev_cb
		self.action_1_cb=action_1_cb
		self.action_2_cb=action_2_cb
		self.index=index

	def next(self):
		# print("MENU NEXT")
		self.index=(self.index+1) % len(self.menu)
		if(self.next_cb):
			if(not self.next_cb(self.menu[self.index])):
				self.next() # if next menu item fails, move to the next. !!hmm - this will get into a loop if no menu item work.!!  

	def prev(self):
		# print("MENU PREV")
		self.index=(self.index-1) % len(self.menu)
		if(self.prev_cb):
			if(not self.prev_cb(self.menu[self.index])):
				self.prev() # as above
	def first(self):
		self.index=0

	def remove(self):
		del self.menu[self.index]

	def action1(self):
		# print("MENU ACTION 1")
		if(self.action_1_cb):
			self.action_1_cb(self.menu[self.index])

	def action2(self):
		# print("MENU ACTION 2")
		if(self.action_2_cb):
			self.action_2_cb(self.menu[self.index])

class MPG123Player:
	SKIP_FWD=":"
	SKIP_BACK=";"
	PAUSE_RESUME="s"
	GET_LOC="k"
	episode=None
	episode_fn=None
	audio_file=None
	loc=0
	proc=None
	last_update=0
	UPDATE_PERIOD=5000

	def __init__(self):
		pass

	def play(self, episode):
		if self.is_alive():
			self.stop()

		self.episode=episode['episode']
		self.episode_fn=episode['episode_fn']
		self.audio_file=episode['episode_fn']+"/episode_audio.mp3"
		try:
			f = open(self.episode_fn+"/episode_loc.txt", "r")
			self.loc = int(f.readline())
			f.close()
		except:
			self.loc=0

		self.proc=pexpect.spawn("mpg123", ["-q", "-m", "--control", "-k "+str(self.loc), self.audio_file])
		self.flush()

	def is_alive(self):
		if self.proc:
			if(self.proc.isalive()): # the process is still running
				return True
			else:
				self.proc.close()
				self.mark_listened()
		return False

	def pause_resume(self):
		if(self.proc):
			dash.add_animation(flash,((0,255,0),10,1))
			self.save_loc()
			self.proc.write(self.PAUSE_RESUME)
			self.flush()

	def stop(self):
		#self.save_loc()
		self.episode=None
		self.episode_fn=None
		if(self.proc):
			self.proc.terminate(force=True)

	def mark_listened():
		if self.proc:
			if(not (self.proc.exitstatus == None)):
				print("not (self.proc.exitstatus == None)")
				if(self.proc.signalstatus == None ): # the player ended naturally
					print("self.proc.signalstatus == None")
					os.path(self.episode_fn+"/episode_listened.txt").touch()
					print("EPISODE: {} marked as listened".format(self.episode))


	def flush(self, t=0):
		if(self.proc):
			try:
				return self.proc.read_nonblocking(timeout=t)
			except:
				pass

	def skip_fwd(self):
		global dash
		dash.add_animation(ffwd_rwd,((255,0,0), -1, 2))
		if(self.proc):
			#self.save_loc()
			self.proc.write(self.SKIP_FWD)
			self.flush()

	def skip_back(self):
		global dash
		dash.add_animation(ffwd_rwd,((255,0,0), 1, 2))
		if(self.proc):
			#self.save_loc()
			self.proc.write(self.SKIP_BACK)
			self.flush()

	def get_loc(self):
		if(self.proc):
			self.flush()
			self.proc.write(self.GET_LOC)
			try:
				self.proc.expect("frame (\d+)")
				self.loc=int(self.proc.match.group(1))
			except:
				return None
		else:
			self.mark_listened()
			return None
		return self.loc

	def save_loc(self):
		if(self.episode_fn):
			self.loc=self.get_loc()
			if(self.loc):
				f = open(self.episode_fn+"/episode_loc.txt", "w")
				f.write(str())
				f.close()

	def mark_listened(self):
		if(self.episode_fn):
			with open(self.episode_fn+"/episode_listened.txt", 'a'):
				os.utime(self.episode_fn+"/episode_listened.txt", None)
			self.stop()

	def tick(self):
		millis=int(round(time.time() * 1000))
		if(millis - self.last_update < self.UPDATE_PERIOD):
			return 
		self.last_update=millis
		self.save_loc()


def get_podcast_list(root_fn):
	podcasts=[]
	for f in os.scandir(root_fn):
		if f.is_dir():
			podcasts.append({
				'podcast':f.name,
				'podcast_fn':f.path,
				'audio': AudioSegment.from_file(f.path+"/podcast_title.wav", format="wav")
				})
	return sorted(podcasts, key=lambda k: k['podcast'])

def get_episode_list(podcast_fn):
	episodes=[]
	for e in os.scandir(podcast_fn):
		if e.is_dir() and not os.path.isfile(e.path+"/episode_listened.txt"):
			episodes.append({
				'episode':e.name,
				'episode_fn':e.path,
				'audio': AudioSegment.from_file(e.path+"/episode_title.wav", format="wav"),
				'pub_date': os.path.getmtime(e.path+"/pub_date.txt"),
				'episode_listened': False
				})
	return sorted(episodes, key=lambda k: k['pub_date'])

def use_podcasts(ignore): # swap knob to navigate podcasts
	global menu
	global menu_mode
	global left_knob

	podcast_list=get_podcast_list("podcasts")
	menu=Menu(podcast_list, say_podcast_title, say_podcast_title, use_episodes, use_podcasts)

	left_knob.when_rotated_clockwise=menu.next
	left_knob.when_rotated_counter_clockwise=menu.prev

	menu.first()
	menu_mode="podcasts"
	say_podcast_title(podcast_list[0])
	return True

def use_episodes(podcast): # swap knob to navigate episodes of the selected podcast
	global menu
	global menu_mode
	global left_knob
	global mpg123

	episode_list=get_episode_list(podcast['podcast_fn'])
	if(len(episode_list) == 0):
		return False
	menu=Menu(episode_list, say_episode_title, say_episode_title, mpg123.play, use_podcasts)

	left_knob.when_rotated_clockwise=menu.next
	left_knob.when_rotated_counter_clockwise=menu.prev

	menu.first()
	menu_mode="episodes"
	say_episode_title(episode_list[0])
	return True

def say_podcast_title(podcast):
	global menu_audio_player
	if(menu_audio_player and menu_audio_player.is_playing()):
		menu_audio_player.stop()
	menu_audio_player=_play_with_simpleaudio(podcast['audio'])
	print("PODCAST:"+ podcast['podcast_fn'])
	return True

def say_episode_title(episode):
	global menu_audio_player
	if(menu_audio_player and menu_audio_player.is_playing()):
		menu_audio_player.stop()
	menu_audio_player=_play_with_simpleaudio(episode['audio'])
	print("EPISODE:"+ episode['episode_fn'])
	return True

# gpiozero Button doesn't do long presses, so we need to measure the length of the press ourselves
left_knob_pressed_ms=0
def left_knob_pressed():
	global left_knob_pressed_ms
	millis=int(round(time.time() * 1000))
	left_knob_pressed_ms = millis

def left_knob_released():
	global left_knob_pressed_ms
	global menu

	LONG_PRESS_MS=500 # how long is a long press in millisecs
	millis=int(round(time.time() * 1000))

	if(millis - left_knob_pressed_ms > LONG_PRESS_MS):
		menu.action2()
	else:
		menu.action1()
	left_knob_pressed_ms=0

right_knob_pressed_ms=0
def right_knob_pressed():
	global right_knob_pressed_ms
	right_knob_pressed_ms = int(round(time.time() * 1000))

def right_knob_released():
	global right_knob_pressed_ms
	global menu

	LONG_PRESS_MS=500 # how long is a long press in millisecs
	millis=int(round(time.time() * 1000))
	if(millis - right_knob_pressed_ms > LONG_PRESS_MS):
		mpg123.mark_listened()
	else:
		mpg123.pause_resume()
	right_knob_pressed_ms=0

def reboot():
	print("Rebooting now")
	os.system("/usr/sbin/reboot --force")

def restart_piradio():
	print("Restarting PiRadio")
	sys.exit(2) # if I die, systemd will start another one of me - I will return stronger

os.chdir(os.path.dirname(sys.argv[0]))

mpg123=MPG123Player()
menu_audio_player=None
podcast_list=get_podcast_list("podcasts")
menu=Menu(podcast_list, say_podcast_title, say_podcast_title, use_episodes, use_podcasts)
say_podcast_title(podcast_list[0])
menu_mode="podcasts"

left_knob=RotaryEncoder(10, 9, bounce_time=0.2)
left_knob.when_rotated_clockwise=menu.next
left_knob.when_rotated_counter_clockwise=menu.prev
left_knob_btn=Button(11)
left_knob_btn.when_pressed = left_knob_pressed
left_knob_btn.when_released = left_knob_released

right_knob=RotaryEncoder(17, 27, bounce_time=0.2)
right_knob.when_rotated_clockwise=mpg123.skip_fwd
right_knob.when_rotated_counter_clockwise=mpg123.skip_back
right_knob_btn=Button(22)
right_knob_btn.when_pressed = right_knob_pressed
right_knob_btn.when_released = right_knob_released

restart_btn=Button(26)
restart_btn.hold_time=2
restart_btn.when_held = reboot
restart_btn.when_released = restart_piradio


neo=neopixel.NeoPixel(board.D12, 32, auto_write=False)
dash=AnimationQ(10)

default_glow=GlowToColour(neo)
default_glow.reset()
dash.set_default_animation(default_glow,((255,80,0), 100))

ffwd_rwd=FfwdRwndAnimator(neo)
ffwd_rwd.reset()
flash=FlashColour(neo)

while(True):
	dash.tick()
	mpg123.tick()





