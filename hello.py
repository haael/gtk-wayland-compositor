#!/usr/bin/python3


"An absolutely useless app displaying the text provided as the argument."


import gi

gi.require_version('Gtk', '4.0')

from gi.repository import Gtk, Pango


if __name__ == '__main__':
	from sys import argv
	
	application = Gtk.Application.new('net.example.hello', 0)
	
	def startup(application):
		application.window = Gtk.ApplicationWindow.new(application)
		
		label = Gtk.Label()
		label.set_text(" ".join(argv[1:]))
		label.set_vexpand(True)
		
		attr_list = Pango.AttrList()
		attr_list.insert(Pango.attr_size_new_absolute(24 * Pango.SCALE))
		attr_list.insert(Pango.attr_weight_new(Pango.Weight.BOLD))
		label.set_attributes(attr_list)
		
		application.window.set_child(label)
	
	application.connect('startup', startup)
	
	def activate(application):
		application.window.present()
	
	application.connect('activate', activate)
	
	try:
		application.run()
	except KeyboardInterrupt:
		print()


