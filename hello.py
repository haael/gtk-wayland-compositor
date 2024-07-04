#!/usr/bin/python3


from sys import argv

import gi

gi.require_version('Gtk', '3.0')

from gi.repository import Gtk


if __name__ == '__main__':
	window = Gtk.Window()
	label = Gtk.Label()
	label.set_text(" ".join(argv[1:]))
	window.add(label)
	window.show_all()

	window.connect('destroy', Gtk.main_quit)
	Gtk.main()


