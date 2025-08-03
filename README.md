# gwayco

Wayland compositor delegating window management to Gtk layout. Written with help of wlroots.

"Gwayco" stands for "Gtk Wayland compositor".

Development status: alpha.


# what?

This project aims to make creating Wayland managers simple.
It consists of two components: the actual server (wlroots) and a Gtk app.
The Gtk app displays a window that is drawn as a desktop and receives create/destroy events from other apps.
For each foreign app window there is a "shadow" widget that can be placed in a Gtk layout.
The server then configures app windows to mimick geometry of the shadow widget.

Making a tiling window manager is as simple as placing Gtk.Box in the root window.


If window manager is not present, the compositor is expected to position windows using some built-in default.


# try it

You can try it from existing X11 or Wayland session. Make sure you have wlroots and Gtk installed together with Python bindings.

From the project's directory run:

`./gwayco.py ./hello.py hello, void`


