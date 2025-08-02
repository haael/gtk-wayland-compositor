#!/usr/bin/python3


import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('GdkWayland', '4.0')

from gi.repository import Gtk, Gdk, GLib, GObject, GdkWayland
from time import time
from cairo import OPERATOR_SOURCE, Region, RectangleInt


print(f"Gtk {Gtk.MAJOR_VERSION}.{Gtk.MINOR_VERSION}.{Gtk.MICRO_VERSION}")


class BuilderExtension:
	def __init__(self, interface, objects):
		self.__builder = Gtk.Builder()
		self.__builder.set_translation_domain(translation)
		self.__builder.add_objects_from_file(interface, objects)
		#self.__builder.connect_signals(self)
	
	def __getattr__(self, attr):
		widget = self.__builder.get_object(attr)
		if widget == None:
			raise AttributeError("Attribute not found in object nor in builder: " + attr)
		return widget


class DesktopLayer(BuilderExtension):
	"Desktop layer. Helper structure holding a single layer of surfaces. Desktop is made of many such layers."
	
	def __init__(self):
		super().__init__('stack.ui', ['bin_layer'])


class Decoration(BuilderExtension):
	def __init__(self):
		super().__init__('decoration.ui', ['box_main'])
		
		self.main_widget = self.box_main
		
		self.active_color = 0.65, 0.65, 0.95, 1.0
		self.inactive_color = 0.75, 0.75, 0.75, 1.0
		self.background_color = self.inactive_color
		
		self.frame_top.set_draw_func(self.draw_frame_top)
		self.frame_top_right.set_draw_func(self.draw_frame_top_right)
		self.frame_right.set_draw_func(self.draw_frame_right)
		self.frame_bottom_right.set_draw_func(self.draw_frame_bottom_right)
		self.frame_bottom.set_draw_func(self.draw_frame_bottom)
		self.frame_bottom_left.set_draw_func(self.draw_frame_bottom_left)
		self.frame_left.set_draw_func(self.draw_frame_left)
		self.frame_top_left.set_draw_func(self.draw_frame_top_left)
		
		#self.box_top.set_app_paintable(True)
		#self.box_top.set_draw_func(self.draw_box_top)
		
		self.drawingarea_icon.set_draw_func(self.draw_icon)
	
	def draw_icon(self, widget, ctx, w, h):
		ctx.set_source_rgba(1, 1, 1, 1)
		ctx.paint()
	
	def draw_box_top(self, widget, ctx, w, h):
		ctx.set_source_rgba(*self.background_color)
		ctx.paint()
	
	def draw_frame_top(self, widget, ctx, w, h):
		ctx.set_source_rgba(*self.background_color)
		ctx.paint()
	
	def draw_frame_top_right(self, widget, ctx, w, h):
		ctx.set_source_rgba(*self.background_color)
		ctx.paint()
	
	def draw_frame_right(self, widget, ctx, w, h):
		ctx.set_source_rgba(*self.background_color)
		ctx.paint()
	
	def draw_frame_bottom_right(self, widget, ctx, w, h):
		ctx.set_source_rgba(*self.background_color)
		ctx.paint()
	
	def draw_frame_bottom(self, widget, ctx, w, h):
		ctx.set_source_rgba(*self.background_color)
		ctx.paint()
	
	def draw_frame_bottom_left(self, widget, ctx, w, h):
		ctx.set_source_rgba(*self.background_color)
		ctx.paint()
	
	def draw_frame_left(self, widget, ctx, w, h):
		ctx.set_source_rgba(*self.background_color)
		ctx.paint()
	
	def draw_frame_top_left(self, widget, ctx, w, h):
		ctx.set_source_rgba(*self.background_color)
		ctx.paint()
	
	def add_window(self, window):
		self.frame_main.set_child(window)


class Desktop:
	def __init__(self):
		self.main_window = Gtk.Window()
		self.main_window.set_can_focus(True)
		
		#self.main_area = Gtk.Stack()
		self.main_area = Gtk.Box()
		#self.main_area = Gtk.Fixed()
		
		self.main_layer = DesktopLayer()
		
		self.main_window.set_child(self.main_layer.bin_layer)
		self.main_layer.frame_main.set_child(self.main_area)
	
	#def __realized(self, window):
	#	wayland_window = window.get_surface()
	#	wayland_window.set_application_id('--desktop')
	#	#window.set_title("eee")
	
	'''
	def __screen_changed(self, window, old_screen):
		screen = window.get_screen()
		visual = screen.get_rgba_visual()
		
		if visual is None:
			visual = screen.get_system_visual()
			self.supports_alpha = False
		else:
			self.supports_alpha = True
		
		window.set_visual(visual)
	
	def __expose_draw(self, window, ctx):
		if self.supports_alpha:
			ctx.set_source_rgba(1.0, 1.0, 1.0, 0.0) 
		else:
			ctx.set_source_rgb(1.0, 1.0, 1.0)
		
		ctx.set_operator(OPERATOR_SOURCE)
		ctx.paint()
	'''
	
	def create_desktop(self, desktop_id):
		self.main_window.set_visible(True)
		self.main_area.set_visible(True)
		self.main_window.get_surface().set_application_id(desktop_id)
		self.main_window.present()
	
	def destroy_desktop(self):
		self.main_window.set_visible(False)
	
	def create_window(self, window):
		decoration = Decoration()
		decoration.label_title.set_text("AAaargh")
		decoration.add_window(window)
		window.decoration = decoration
		
		#self.main_area.add_named(decoration.main_widget, str(time()))
		self.main_area.append(decoration.main_widget)
		#self.main_area.put(decoration.main_widget, 100, 100)
		#decoration.main_widget.set_size_request(300, 400)
		
		window.set_visible(True)
	
	def destroy_window(self, window):
		self.main_area.remove(window.decoration.main_widget)
		#self.main_area.remove(window)
	
	def map_window(self, window):
		window.decoration.main_widget.set_visible(True)
		#window.set_visible(True)
	
	def unmap_window(self, window):
		window.decoration.main_widget.set_visible(False)
		#window.set_visible(False)
	
	def focus_window(self, window):
		#self.main_stack.set_visible_child(window.decoration)
		window.decoration.background_color = window.decoration.active_color
		window.decoration.main_widget.queue_draw()
		window.grab_focus()
	
	def unfocus_window(self, window):
		window.decoration.background_color = window.decoration.inactive_color
		window.decoration.main_widget.queue_draw()
		self.main_window.grab_focus()
		pass


class Rectangle(GObject.Object):
	__name__ = 'Rectangle'
	
	def __init__(self, x, y, width, height):
		super().__init__()
		self.x = x
		self.y = y
		self.width = width
		self.height = height
	
	def cmp(self, other):
		if other is None:
			return False
		
		try:
			return self.x == other.x and self.y == other.y and self.width == other.width and self.height == other.height
		except AttributeError:
			return False


class ClientWindow(Gtk.Widget):
	"A widget that doesn't draw anything but reacts to positioning, size allocation and focusing."
	
	__gsignals__ = {
		'request-close': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, ()),
		'request-anchor': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, (GObject.TYPE_UINT, GObject.TYPE_INT)),
		'request-margins': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, (GObject.TYPE_INT, GObject.TYPE_INT, GObject.TYPE_INT, GObject.TYPE_INT)),
		'request-opacity': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, (GObject.TYPE_FLOAT,)),
		'notify-presentation': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, (GObject.TYPE_UINT,)),
		'size-allocate': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, (GObject.TYPE_OBJECT,))
	}
	
	def __init__(self):
		super().__init__()
		#self.set_has_window(False)
		self.set_can_focus(True)
		self.last_allocation = None
	
	def do_size_allocate(self, *args):
		y, b = self.compute_bounds(self.get_root())
		if not y: return
		r = Rectangle(b.get_x(), b.get_y(), b.get_width(), b.get_height())
		if not r.cmp(self.last_allocation):
			self.last_allocation = r
			self.emit('size-allocate', r)


class Manager(GObject.Object):
	__gsignals__ = {
		'show-window': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, (GObject.TYPE_UINT,)),
		'hide-window': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, (GObject.TYPE_UINT,)),
		'set-geometry': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, (GObject.TYPE_UINT, GObject.TYPE_INT, GObject.TYPE_INT, GObject.TYPE_INT, GObject.TYPE_INT)),
		'grab-focus': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, (GObject.TYPE_UINT,)),
		'drop-focus': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, (GObject.TYPE_UINT,)),
		'request-close': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, (GObject.TYPE_UINT,)),
		'request-anchor': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, (GObject.TYPE_UINT, GObject.TYPE_UINT, GObject.TYPE_INT)),
		'request-margins': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, (GObject.TYPE_UINT, GObject.TYPE_INT, GObject.TYPE_INT, GObject.TYPE_INT, GObject.TYPE_INT)),
		'request-opacity': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, (GObject.TYPE_UINT, GObject.TYPE_FLOAT,)),
		'notify-presentation': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, (GObject.TYPE_UINT, GObject.TYPE_UINT))
	}
	
	def __init__(self):
		super().__init__()
		self.desktops = {}
		self.windows = {}
	
	def create_desktop(self, desktop_id):
		desktop = Desktop()
		self.desktops[desktop_id] = desktop
		desktop.create_desktop(desktop_id)
	
	def destroy_desktop(self, desktop_id):
		self.desktops[desktop_id].destroy_desktop()
		del self.desktops[desktop_id]
	
	def create_window(self, window_id, desktop_id):
		window = ClientWindow()
		window.desktop = self.desktops[desktop_id]
		self.windows[window_id] = window
		
		a = window.connect('map', lambda _window: self.emit('show-window', window_id))
		b = window.connect('unmap', lambda _window: self.emit('hide-window', window_id))
		c = window.connect('size-allocate', lambda _window, rect: self.emit('set-geometry', window_id, int(rect.x), int(rect.y), int(rect.width), int(rect.height)))
		#d = window.connect('focus-in-event', lambda _window, _: self.emit('grab-focus', window_id))
		#e = window.connect('focus-out-event', lambda _window, _: self.emit('drop-focus', window_id))
		f = window.connect('request-close', lambda _window, *_params: self.emit('request-close', window_id, *_params))
		g = window.connect('request-anchor', lambda _window, *_params: self.emit('request-anchor', window_id, *_params))
		h = window.connect('request-margins', lambda _window, *_params: self.emit('request-margins', window_id, *_params))
		i = window.connect('request-opacity', lambda _window, *_params: self.emit('request-opacity', window_id, *_params))
		j = window.connect('notify-presentation', lambda _window, *_params: self.emit('notify-presentation', window_id, *_params))
		
		window.__signals = a, b, c, f, g, h, i, j
		
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
	
	def set_margins(self, window_id, left, top, right, bottom):
		...
	
	def set_title(self, title):
		...


if __name__ == '__main__':
	from locale import gettext, bindtextdomain, textdomain
	from sys import stdout, stderr
	from os import read, environ
	
	#for key, value in environ.items():
	#	print(key, value, file=stderr)
	
	translation = 'haael_wayland_desktop'
	locale = 'locale'
	
	bindtextdomain(translation, locale)
	textdomain(translation)
	
	manager = Manager()
	manager.connect('show-window', lambda _manager, *args: print('show_window', args))
	manager.connect('hide-window', lambda _manager, *args: print('hide_window', args))
	manager.connect('set-geometry', lambda _manager, *args: print('set_geometry', args))
	manager.connect('grab-focus', lambda _manager, *args: print('grab_focus', args))
	manager.connect('drop-focus', lambda _manager, *args: print('drop_focus', args))
	manager.connect('request-close', lambda _manager, *args: print('request-close', args))
	manager.connect('request-anchor', lambda _manager, *args: print('request-anchor', args))
	manager.connect('request-margins', lambda _manager, *args: print('request-margins', args))
	manager.connect('request-opacity', lambda _manager, *args: print('request-opacity', args))
	manager.connect('notify-presentation', lambda _manager, *args: print('notify-presentation', args))
	
	mainloop = GLib.MainLoop()
	
	try:
		#manager.create_desktop(1)
		
		#manager.create_window(2, 1)
		#manager.map_window(2)
		#manager.focus_window(2)
		#manager.unfocus_window(2)
		#manager.destroy_window(2)
		
		#manager.create_window(3, 1)
		#manager.map_window(3)
		#manager.focus_window(3)
		
		mainloop.run()
	except KeyboardInterrupt:
		print()




