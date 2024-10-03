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

`./compositor.py seat0 ./desktop.py`

Make sure to use the correct "seat" which is `seat0` for most people.

A window should appear, with the Glade layout as chosen by `desktop.py`.
Find the name of Wayland socket in the logs, which should be `wayland-0` if you are running under X11 or `wayland-1` if from inside other Wayland session.

Then try connecting some desktop apps to the server.
You may use the provided `hello.py` that accepts arguments and displays them as a label.

```
GDK_BACKEND=wayland WAYLAND_DISPLAY=wayland-0 ./hello.py one one one
GDK_BACKEND=wayland WAYLAND_DISPLAY=wayland-0 ./hello.py two two two
```

The new app window show should be added to a layout, making it a very simple tiling window manager.

