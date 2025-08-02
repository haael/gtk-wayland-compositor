#!/usr/bin/python3


import gi

gi.require_version('Gtk', '3.0')

from gi.repository import Gtk, GLib, GObject
from time import time


class BuilderExtension:
	def __init__(self, interface, translation, objects):
		self.__builder = Gtk.Builder()
		self.__builder.set_translation_domain(translation)
		self.__builder.add_objects_from_file(interface, objects)
		self.__builder.connect_signals(self)
	
	def __getattr__(self, attr):
		window_idget = self.__builder.get_object(attr)
		if window_idget == None:
			raise AttributeError("Attribute not found in object nor in builder: " + attr)
		return window_idget


class DesktopLayer(BuilderExtension):
	"Desktop layer. Helper structure holding a single layer of surfaces. Desktop is made of many such layers."
	
	def __init__(self, translation):
		super().__init__('stack.glade', translation, ['bin_layer'])


class Desktop(BuilderExtension):
	"Desktop window. Main structure holding all UI elements per monitor."
	
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
		"Add a new toplevel window to the UI hierarchy."
		toplevel.desktop = self
		self.toplevel_stack.add_named(toplevel, str(time()))
	
	def remove_toplevel(self, toplevel):
		"Remove the toplevel window from hierarchy."
		self.toplevel_stack.remove(toplevel)
		try:
			next_toplevel = self.toplevel_stack.get_children()[0]
		except IndexError:
			pass
		else:
			self.activate_toplevel(next_toplevel)
		self.toplevel_stack.queue_draw()
	
	def activate_toplevel(self, toplevel):
		"Activate the toplevel window by bringing it on top of the stack."
		self.toplevel_stack.set_visible_child(toplevel)
	
	def deactivate_toplevel(self, toplevel):
		"Deactivate the toplevel window by greying it out or showing another window on top."
		pass


class WaylandSurface:
	def __init__(self, identifier):
		self.identifier = identifier
		
		self.connect('map', lambda _widget, *args: message_out('map', identifier))
		self.connect('unmap', lambda _widget, *args: message_out('unmap', identifier))
		self.connect('size-allocate', lambda _widget, rect: message_out('set_window_geometry', identifier, rect.x, rect.y, rect.window_idth, rect.height))
		self.connect('focus-in-event', lambda _widget, *args: message_out('focus', identifier))


class Toplevel(Gtk.Widget, WaylandSurface):
	"window_idget representing wayland toplevel surface. Resizing it will send signals to the window manager."
	
	__gtype_name__ = 'Toplevel'
	
	def __init__(self, identifier):
		Gtk.window_idget.__init__(self)
		self.set_has_window(False)
		self.set_can_focus(True)
		WaylandSurface.__init__(self, identifier)
	
	def wayland_activate(self):
		"Request from the compositor to activate (focus) the surface. The surface will be in mapped state. The surface should be brought to the top and should receive keyboard focus."
		self.desktop.activate_toplevel(self)
		print("toplevel activate", file=stderr)
		self.grab_focus()
	
	def wayland_deactivate(self):
		"Request from the compositor to deactivate (unfocus, grey out) the surface. The surface will be in mapped state."
		self.desktop.deactivate_toplevel(self)
		print("toplevel deactivate", file=stderr)
	
	def wayland_map(self):
		"Request from the compositor to map (show) the surface. The surface does not need to be shown on the top but should be positioned and added to a list of visible windows."
		#self.show()
	
	def wayland_unmap(self):
		"Request from the compositor to unmap (hide) the surface. The window MUST be hidden as its contents may be garbage and no input events should be sent to it."
		#self.hide()


class Popup(Gtk.Window, WaylandSurface):
	"window_idget representing wayland popup surface."
	
	__gtype_name__ = 'Popup'
	
	def __init__(self, identifier):
		Gtk.window_idget.__init__(self)
		self.set_has_window(False)
		#self.set_focusable(True)
		WaylandSurface.__init__(self, identifier)


class Manager:
	"Window manager. Holds a list of outputs (monitors), desktops, toplevel windows and popups."
	
	def __init__(self, translation):
		self.translation = translation
		self.outputs = {}
		self.toplevels = {}
		self.popups = {}
	
	def new_output(self, id_):
		"New monitor has been connected. Create a desktop window."
		self.outputs[id_] = Desktop(self.translation)
		self.outputs[id_].window_main.show_all()
	
	def output_destroy(self, id_):
		self.outputs[id_].window_main.hide()
		self.outputs[id_].window_main.close()
		#del self.outputs[id_] # FIXME: remove output after all surfaces have been removed
	
	def new_toplevel(self, id_):
		"New toplevel surface created. Add it to one of the desktops."
		toplevel = self.toplevels[id_] = Toplevel(id_)
		desktop = list(self.outputs.values())[0]
		desktop.add_toplevel(toplevel)
	
	def toplevel_destroy(self, id_):
		if id_ in self.toplevels:
			desktop = list(self.outputs.values())[0]
			desktop.remove_toplevel(self.toplevels[id_])
			del self.toplevels[id_]
	
	def new_popup(self, id_):
		"New popup surface created. Popups always have a parent and will be displayed on the same output as the parent."
		self.popups[id_] = Popup(id_)
	
	def popup_destroy(self, id_):
		if id_ in self.popups:
			del self.popups[id_]




class Desktop:
	def __init__(self):
		self.main_window = Gtk.Window()
		self.main_stack = Gtk.Stack()
		self.main_window.add(self.main_stack)
	
	def create(self):
		self.main_window.show()
		self.main_stack.show()
	
	def destroy(self):
		self.main_window.hide()
	
	def create_window(self, window):
		decoration = Gtk.Frame()
		decoration.add(window)
		window.decoration = decoration
		self.add_named(decoration, )
		window.show()
	
	def destroy_window(self, window):
		self.remove(window.decoration)
	
	def map_window(self, window):
		window.decoration.show()
	
	def unmap_window(self, window):
		window.decoration.hide()
	
	def focus_window(self, window):
		self.main_stack.set_visible_child(window.decoration)
		window.grab_focus()
	
	def unfocus_window(self, window):
		self.main_window.grab_focus()


class new_Manager(GObject.Object):
	__gsignals__ = {
		'show-window': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, (GObject.TYPE_UINT,)),
		'hide-window': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, (GObject.TYPE_UINT,)),
		'set-geometry': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, (GObject.TYPE_UINT, GObject.TYPE_INT, GObject.TYPE_INT, GObject.TYPE_INT, GObject.TYPE_INT)),
		'grab-focus': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, (GObject.TYPE_UINT,)),
		'drop-focus': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, (GObject.TYPE_UINT,))
	}
	
	def __init__(self):
		self.desktops = {}
		self.windows = {}
	
	def create_desktop(self, desktop_id):
		desktop = Desktop()
		self.desktops[desktop_id] = desktop
		desktop.create()
	
	def destroy_desktop(self, desktop_id):
		self.desktops[desktop_id].destroy()
		del self.desktops[desktop_id]
	
	def create_window(self, window_id, desktop_id):
		window = Gtk.Widget()
		window.desktop = self.desktops[desktop_id]
		self.windows[window_id] = window
		
		window.set_has_window(False)
		window.set_can_focus(True)
		a = window.connect('show', lambda _window: self.emit('show-window', window_id))
		b = window.connect('hide', lambda _window: self.emit('hide-window', window_id))
		c = window.connect('size-allocate', lambda _window, rect: self.emit('set-geometry', window_id, rect.x, rect.y, rect.window_idth, rect.height))
		d = window.connect('focus-in-event', lambda _window: self.emit('grab-focus', window_id))
		e = window.connect('focus-out-event', lambda _window: self.emit('drop-focus', window_id))
		window.__signals = [a, b, c, d, e]
		
		window.desktop.create_window(window)
	
	def destroy_window(self, window_id):
		window = self.windows[window_id]
		window.desktop.destroy_window(window)
		for s in window.__signals:
			window.disconnect(s)
		del self.windows[window_id]
	
	def map_window(self, window_id):
		window = self.windows[window_id]
		window.desktop.map_window(window)
	
	def unmap_window(self, window_id):
		window = self.windows[window_id]
		window.desktop.unmap_window(window)
	
	def focus_window(self, window_id):
		window = self.windows[window_id]
		window.desktop.focus_window(window)
	
	def unfocus_window(self, window_id):
		window = self.windows[window_id]
		window.desktop.unfocus_window(window)
	
	def set_opacity(self, window_id, opacity):
		window = self.windows[window_id]
		window.desktop.set_opacity(window)
	
	def set_decorations(self, window_id, decorated, decorations): #movable, resizable, deletable
		...
	
	def set_presentation(self, window_id, presentation): #minimized, iconified, normal, maximized, fullscreen
		...
	
	def set_anchor(self, window_id, anchor, strut): #left, top, right, bottom, center
		...


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
		
		'''
		
		create_desktop desktop_id
		destroy_desktop desktop_id
		
		create_window window_id (desktop_id)
		destroy_window window_id
		
		map_window window_id
		unmap_window window_id
		
		focus_window window_id
		unfocus_window window_id
		
		set_transparency window_id (n)
		set_decorations window_id (movable, resizable, deletable, decorated)
		set_presentation window_id (minimized, iconified, normal, maximized, fullscreen)
		set_anchor window_id (left | top | right | bottom | center)
		set_strut window_id (n)
		
		show window_id
		hide window_id
		geometry window_id x y w h
		focus window_id
		unfocus window_id
		
		'''


		match msg.split():
			case [msg_id, 'new_output', 'OUTPUT', output_id]:
				manager.new_output(output_id)
				message_out('@', msg_id)
			case [msg_id, 'output_destroy', 'OUTPUT', output_id]:
				manager.output_destroy(output_id)
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
			
			case [msg_id, 'quit', _, _]:
				mainloop.quit()
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




