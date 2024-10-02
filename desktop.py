#!/usr/bin/python3


import gi

gi.require_version('Gtk', '3.0')

from gi.repository import Gtk, GLib
from time import time


class BuilderExtension:
	def __init__(self, interface, translation, objects):
		self.__builder = Gtk.Builder()
		self.__builder.set_translation_domain(translation)
		self.__builder.add_objects_from_file(interface, objects)
		self.__builder.connect_signals(self)
	
	def __getattr__(self, attr):
		widget = self.__builder.get_object(attr)
		if widget == None:
			raise AttributeError("Attribute not found in object nor in builder: " + attr)
		return widget


class DesktopLayer(BuilderExtension):
	def __init__(self, translation):
		super().__init__('stack.glade', translation, ['bin_layer'])


class Desktop(BuilderExtension):
	def __init__(self, translation):
		super().__init__('desktop.glade', translation, ['window_main'])
		
		self.background_layer = DesktopLayer(translation)
		self.bottom_layer = DesktopLayer(translation)
		self.middle_layer = DesktopLayer(translation)
		self.top_layer = DesktopLayer(translation)
		self.overlay_layer = DesktopLayer(translation)
		
		self.overlay_main.add_overlay(self.background_layer.bin_layer)
		self.overlay_main.add_overlay(self.bottom_layer.bin_layer)
		self.overlay_main.add_overlay(self.middle_layer.bin_layer)
		self.overlay_main.add_overlay(self.top_layer.bin_layer)
		self.overlay_main.add_overlay(self.overlay_layer.bin_layer)
		
		self.toplevel_stack = Gtk.Stack()
		self.middle_layer.frame_main.add(self.toplevel_stack)
	
	def add_toplevel(self, toplevel):
		toplevel.desktop = self
		self.toplevel_stack.add_named(toplevel, str(time()))
		toplevel.show()
		self.toplevel_stack.set_visible_child(toplevel)
	
	def remove_toplevel(self, toplevel):
		toplevel.hide()
		self.toplevel_stack.remove(toplevel)
		try:
			next_toplevel = self.toplevel_stack.get_children()[0]
		except IndexError:
			pass
		else:
			next_toplevel.show()
			self.toplevel_stack.set_visible_child(next_toplevel)
		self.toplevel_stack.queue_draw()
	
	def activate_toplevel(self, toplevel):
		self.toplevel_stack.set_visible_child(toplevel)
	
	def deactivate_toplevel(self, toplevel):
		#self.toplevel_stack.remove(toplevel)
		pass


class WaylandSurface:
	def __init__(self, identifier):
		self.identifier = identifier
		
		self.connect('map', lambda widget, *args: message_out('map', identifier))
		self.connect('unmap', lambda widget, *args: message_out('unmap', identifier))
		self.connect('size-allocate', lambda widget, rect: message_out('set_window_geometry', identifier, rect.x, rect.y, rect.width, rect.height))
		self.connect('focus-in-event', lambda widget, *args: message_out('focus', identifier))


class Toplevel(Gtk.Widget, WaylandSurface):
	"Widget representing wayland toplevel surface. Resizing it will send signals to the window manager."
	
	__gtype_name__ = 'Toplevel'
	
	def __init__(self, identifier):
		Gtk.Widget.__init__(self)
		self.set_has_window(False)
		self.set_can_focus(True)
		WaylandSurface.__init__(self, identifier)
	
	def wayland_activate(self):
		self.desktop.activate_toplevel(self)
		print("toplevel activate", file=stderr)
		self.grab_focus()
	
	def wayland_deactivate(self):
		self.desktop.deactivate_toplevel(self)
		print("toplevel deactivate", file=stderr)


class Popup(Gtk.Widget, WaylandSurface):
	"Widget representing wayland popup surface."
	
	__gtype_name__ = 'Popup'
	
	def __init__(self, identifier):
		Gtk.Widget.__init__(self)
		self.set_has_window(False)
		#self.set_focusable(True)
		WaylandSurface.__init__(self, identifier)


class Manager:
	def __init__(self, translation):
		self.translation = translation
		self.outputs = {}
		self.toplevels = {}
		self.popups = {}
	
	def new_output(self, id_):
		self.outputs[id_] = Desktop(self.translation)
		self.outputs[id_].window_main.show_all()
	
	def new_toplevel(self, id_):
		toplevel = self.toplevels[id_] = Toplevel(id_)
		desktop = list(self.outputs.values())[0]
		desktop.add_toplevel(toplevel)
	
	def toplevel_destroy(self, id_):
		if id_ in self.toplevels:
			desktop = list(self.outputs.values())[0]
			desktop.remove_toplevel(self.toplevels[id_])
			del self.toplevels[id_]
	
	def new_popup(self, id_):
		self.popups[id_] = Popup(id_)
	
	def popup_destroy(self, id_):
		if id_ in self.popups:
			del self.popups[id_]
	

if __name__ == '__main__':
	from locale import gettext, bindtextdomain, textdomain
	from sys import stdout, stderr
	from os import read, environ
	
	for key, value in environ.items():
		print(key, value, file=stderr)
	
	translation = 'haael_wayland_desktop'
	locale = 'locale'
	
	bindtextdomain(translation, locale)
	textdomain(translation)
	
	manager = Manager(translation)
	
	def message_in(msg):
		print("received:", msg, file=stderr)
		match msg.split():
			case [msg_id, 'new_output', 'OUTPUT', output_id]:
				manager.new_output(output_id)
				message_out('@', msg_id)
			
			case [msg_id, 'new_surface', 'TOPLEVEL', surface_id]:
				manager.new_toplevel(surface_id)
				message_out('@', msg_id)
			case [msg_id, 'surface_destroy', 'TOPLEVEL', surface_id]:
				manager.toplevel_destroy(surface_id)
				message_out('@', msg_id)
			case [msg_id, method_name, 'TOPLEVEL', surface_id]:
				if surface_id in manager.toplevels:
					try:
						method = getattr(manager.toplevels[surface_id], 'wayland_' + method_name)
					except AttributeError:
						print("no method:", 'wayland_' + method_name, file=stderr)
					else:
						method()
				message_out('@', msg_id)
			
			case [msg_id, 'new_surface', 'POPUP', surface_id]:
				manager.new_popup(surface_id)
				message_out('@', msg_id)
			case [msg_id, 'surface_destroy', 'POPUP', surface_id]:
				manager.popup_destroy(surface_id)
				message_out('@', msg_id)
			case [msg_id, method_name, 'POPUP', surface_id]:
				if surface_id in manager.popups:
					try:
						method = getattr(manager.popups[surface_id], 'wayland_' + method_name)
					except AttributeError:
						print("no method:", 'wayland_' + method_name, file=stderr)
					else:
						method()
				message_out('@', msg_id)
	
	message_id = 0
	
	def message_out(*args):
		global message_id
		print("sent:", args, file=stderr)
		print(message_id, *args)
		message_id += 1
		stdout.flush()
	
	def data_in(fd, condition):
		if condition & GLib.IO_IN:
			data = read(fd, 256).decode('utf-8')
			assert(data[-1] == "\n")
			
			for ss in data.split("\n"):
				if ss:
					message_in(ss)
		
		elif condition & GLib.IO_HUP:
			mainloop.quit()
		
		return True
	
	GLib.io_add_watch(0, GLib.IO_IN | GLib.IO_HUP, data_in)
	
	mainloop = GLib.MainLoop()
	
	try:
		mainloop.run()
	except KeyboardInterrupt:
		print()




