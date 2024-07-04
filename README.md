# gtk-wayland-compositor
Wayland compositor delegating window management to Gtk layout

Status: alpha

Language: Python

# what?

This project aims to make creating Wayland managers simple.
It consists of two components: the actual server (wlroots) and a Gtk app.
The Gtk app displays a window that is drawn as a desktop and receives create/destroy events from other apps.
For each foreign app window there is a "shadow" widget that can be placed in a Gtk layout.
The server then configures app windows to mimick geometry of the shadow widget.

Making a tiling window manager is as simple as placing Gtk.Box in the root window.
