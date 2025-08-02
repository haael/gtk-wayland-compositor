#!/usr/bin/python3


"An absolutely useless app that displays random kitten images in multiple windows."


import gi

gi.require_version('Gtk', '4.0')


from gi.repository import Gtk
from pathlib import Path
from random import choice


def startup(application):
	application.windows = []
	show_kitten(application, 'one', random_kitten())


def activate(application):
	application.windows[0].present()


def hide_kitten(application, window):
	application.windows.remove(window)


def show_kitten(application, title, filename):
	window = Gtk.ApplicationWindow.new(application)
	window.set_title(title)
	vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
	window.set_child(vbox)
	aspect_frame = Gtk.AspectFrame()
	aspect_frame.set_vexpand(True)
	vbox.append(aspect_frame)
	image = Gtk.Image.new_from_file(filename)
	aspect_frame.set_child(image)
	hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
	vbox.append(hbox)
	close_button = Gtk.Button()
	close_button.set_label("close")
	app_id_entry = Gtk.Entry()
	more_button = Gtk.Button()
	more_button.set_label("more")
	hbox.append(close_button)
	hbox.append(app_id_entry)
	app_id_entry.set_hexpand(True)
	hbox.append(more_button)
	app_id_entry.set_text(title)
	window.connect('close-request', lambda *_: hide_kitten(application, window))
	close_button.connect('clicked', lambda *_: window.close())
	more_button.connect('clicked', lambda *_: show_kitten(application, app_id_entry.get_text(), random_kitten()).present())
	application.windows.append(window)
	return window


def random_kitten():
	return str(choice(list(Path('kittens').iterdir())))


if __name__ == '__main__':
	application = Gtk.Application.new('net.example.kittens', 0)
	application.connect('startup', startup)
	application.connect('activate', activate)
	try:
		application.run()
	except KeyboardInterrupt:
		print()


