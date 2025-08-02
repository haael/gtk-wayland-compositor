#!/usr/bin/python3


from enum import Enum
from types import SimpleNamespace

from subprocess import Popen, PIPE


Status = Enum('Status', 'away inactive busy online active')


Mode = Enum('Mode', 'light dark')


class State:
	names = set()
	
	def __set_name__(self, owner, name):
		self.names.add(name)
		self.name = name
	
	def __get__(self, instance, owner=None):
		return getattr(instance, '_' + self.__class__.__name__ + '__' + self.name)
	
	def __set__(self, instance, value):
		setattr(instance, '_' + self.__class__.__name__ + '__' + self.name, value)
		instance.restart_apps()
	
	def __delete__(self, instance):
		delattr(instance, '_' + self.__class__.__name__ + '__' + self.name)


class Session:
	status:Status = State()
	mode:Mode = State()
	offline:bool = State()
	screen_blank:bool = State()
	input_lock:bool = State()
	mute:bool = State()
	suspend:bool = State()
	fullscreen:bool = State()
	mic_off:bool = State()
	camera_off:bool = State()
	configuration:bool = State()
	
	def __init__(self):
		self.status = Status.offline	# User activity status.
		self.mode = Mode.light			# Light/dark mode.
		self.offline = True				# Networking / offline.
		self.screen_blank = False		# Screen visible / blank.
		self.input_lock = False			# Input active / password protected.
		self.mute = False				# Sound enabled / muted.
		self.suspend = False			# User apps active / suspended.
		self.fullscreen = False			# Some app taking full screen.
		self.mic_off = False			# Mic off / on.
		self.camera_off = False			# Camera off / on.
		self.configuration = False		# Configuration mode.
		
		self.active_apps = {}
		self.available_apps = {}
	
	def spawn_command(self, cmd):
		return Popen(cmd)
	
	def restart_apps(self):
		killed_apps = []
		
		for cmd, conditions in self.available_apps.items():
			enabled = True
			for name in State.names:
				state = getattr(self, name)
				condition = getattr(conditions, name, ...)
				if condition is not Ellipsis:
					enabled &= state in condition
			
			if not enabled and cmd in self.active_apps:
				app = self.active_apps[cmd].process
				del self.active_apps[cmd]
				killed_apps.append(app)
				app.terminate() # Kill app.
			elif enabled and cmd not in self.active_apps:
				self.active_apps[cmd] = SimpleNamespace(process=self.spawn_command(cmd), failures=0) # Spawn app.
		
		for app in killed_apps:
			app.wait()
	
	def child_died(self, app):
		cmd = app.cmd
		if cmd not in self.active_apps:
			return # Not an error.
		self.active_apps[cmd].failures += 1
		
		if self.active_apps[cmd].failures < 3:
			self.active_apps[cmd].process = self.spawn_command(cmd)
		else:
			del self.active_apps[cmd]


