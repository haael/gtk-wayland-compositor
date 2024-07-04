#!/usr/bin/python3


import gi

gi.require_version('Gtk', '3.0')

from gi.repository import Gtk, GLib


class BuilderExtension:
	def __init__(self, interface, translation, objects):
		self.builder = Gtk.Builder()
		self.builder.set_translation_domain(translation)
		self.builder.add_objects_from_file(interface, objects)
		self.builder.connect_signals(self)
	
	def __getattr__(self, attr):
		widget = self.builder.get_object(attr)
		if widget != None:
			setattr(self, attr, widget)
			return widget
		else:
			raise AttributeError("Attribute not found in object nor in builder: " + attr)


class Desktop(BuilderExtension):
	def quit(self, widget):
		mainloop.quit()


class WaylandSurface:
	def __init__(self, identifier):
		self.identifier = identifier
		
		self.connect('map', lambda widget: message_out('map', identifier))
		self.connect('unmap', lambda widget: message_out('unmap', identifier))
		self.connect('size-allocate', lambda widget, rect: message_out('set_window_geometry', identifier, rect.x, rect.y, rect.width, rect.height))
		self.connect('focus-in-event', lambda widget: message_out('focus', identifier))


class Toplevel(Gtk.Widget, WaylandSurface):
	__gtype_name__ = 'Toplevel'
	
	def __init__(self, identifier):
		Gtk.Widget.__init__(self)
		self.set_has_window(False)
		WaylandSurface.__init__(self, identifier)


class Popup(Gtk.Widget, WaylandSurface):
	__gtype_name__ = 'Popup'
	
	def __init__(self, identifier):
		Gtk.Widget.__init__(self)
		self.set_has_window(False)
		WaylandSurface.__init__(self, identifier)


class Manager:
	def __init__(self, desktop_interface, translation):
		self.translation = translation
		self.desktop_interface = desktop_interface
		self.outputs = {}
		self.toplevels = {}
		self.popups = {}
	
	def new_output(self, id_):
		self.outputs[id_] = Desktop(self.desktop_interface, self.translation, ['desktop_window'])
		self.outputs[id_].desktop_window.show_all()
	
	def new_toplevel(self, id_):
		self.toplevels[id_] = Toplevel(id_)
		list(self.outputs.values())[0].tiling_box.pack_start(self.toplevels[id_], True, True, 0)
		self.toplevels[id_].show()
	
	def toplevel_destroy(self, id_):
		if id_ in self.toplevels:
			list(self.outputs.values())[0].tiling_box.remove(self.toplevels[id_])
			del self.toplevels[id_]
	
	def new_popup(self, id_):
		self.popups[id_] = Popup(id_)
	
	def popup_destroy(self, id_):
		if id_ in self.popups:
			del self.popups[id_]
	

if __name__ == '__main__':
	from locale import gettext, bindtextdomain, textdomain
	from sys import stdout, stderr
	
	interface = 'tiling.glade'
	translation = 'haael_wayland_desktop'
	locale = 'locale'
	
	bindtextdomain(translation, locale)
	textdomain(translation)
	
	manager = Manager(interface, translation)
	
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
						pass
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
						pass
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
		channel = GLib.IOChannel.unix_new(fd)
		if condition & GLib.IO_IN:
			data = channel.read_line()
			message_in(data.str_return[:-1])
		elif condition & GLib.IO_HUP:
			mainloop.quit()
		
		return True
	
	GLib.io_add_watch(0, GLib.IO_IN | GLib.IO_HUP, data_in)
	
	mainloop = GLib.MainLoop()
	
	try:
		mainloop.run()
	except KeyboardInterrupt:
		print()




