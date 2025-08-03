#!/usr/bin/python3


__author__ = "haael"
__copyright__ = "Copyright © 2024-2025 haael"
__license__ = "MIT"
__version__ = "2025.08.02.22541aa"
__status__ = "α"


import sys
from logging import basicConfig, getLogger, DEBUG, INFO, WARNING, ERROR


try:
	option_args_n = [_arg.startswith('--') for _arg in sys.argv[1:]].index(False) + 1
except ValueError:
	option_args_n = len(sys.argv)


loglevels = {'debug':DEBUG, 'infos':INFO, 'warnings':WARNING, 'errors':ERROR, 'silent':ERROR + 1}

gwayco_loglevel = INFO

wlroots_loglevel = WARNING

for keyword, level in loglevels.items():
	if '--gwayco-' + keyword in sys.argv[:option_args_n]:
		gwayco_loglevel = level
	
	if '--wlroots-' + keyword in sys.argv[:option_args_n]:
		wlroots_loglevel = level


basicConfig(level=gwayco_loglevel)
logger = getLogger('gwayco')

from wlroots.util.log import log_init
log_init(wlroots_loglevel)

from wlroots import ffi, version as wlroots_version
from wlroots.helper import build_compositor
from wlroots.wlr_types import Cursor, DataDeviceManager, OutputLayout, Scene, Seat, XCursorManager, XdgShell, InputDevice, Output, SceneNodeType, SceneSurface, SceneBuffer, Buffer

from wlroots.wlr_types.idle_notify_v1 import IdleNotifierV1
from wlroots.wlr_types.layer_shell_v1 import LayerShellV1, LayerSurfaceV1
from wlroots.wlr_types.foreign_toplevel_management_v1 import ForeignToplevelManagerV1
from wlroots.wlr_types.xdg_decoration_v1 import XdgDecorationManagerV1, XdgToplevelDecorationV1, XdgToplevelDecorationV1Mode
from wlroots.wlr_types.server_decoration import ServerDecorationManager, ServerDecorationManagerMode

from wlroots.wlr_types.scene import SceneNode, SceneRect, SceneBuffer, SceneTree, SceneOutput
from wlroots.wlr_types.cursor import WarpMode
from wlroots.wlr_types.input_device import ButtonState, InputDeviceType
from wlroots.wlr_types.keyboard import Keyboard, KeyboardModifier, KeyboardKeyEvent
from wlroots.wlr_types.pointer import Pointer, PointerButtonEvent, PointerMotionAbsoluteEvent, PointerMotionEvent
from wlroots.wlr_types.touch import Touch
from wlroots.wlr_types.seat import RequestSetSelectionEvent
from wlroots.wlr_types.xdg_shell import XdgSurface, XdgSurfaceRole
from wlroots.util.clock import Timespec

from pywayland.server import Display, Client, Listener
from pywayland.protocol.wayland import WlKeyboard, WlSeat
from xkbcommon import xkb

from itertools import product, chain
from collections import defaultdict


class WlList:
	"Direct access to WlList c-structure."
	
	def __init__(self, ptr, type, link, child_cls):
		self.__ptr = ptr
		self.__type = type
		self.__link = link
		self.__child_cls = child_cls
	
	def __len__(self):
		children = self.__ptr
		if children.next == children:
			return 0
		
		l = 1
		child = children.next
		while child != children.prev:
			child = child.next
			l += 1
		return l
	
	def __getitem__(self, index):
		children = self.__ptr
		if children.next == children:
			raise IndexError
		
		if index < 0:
			index = len(self) - index
		
		l = 0
		child = children.next
		while l != index and child != children.prev:
			child = child.next
			l += 1
		
		if l != index:
			raise IndexError
		
		ptr = ffi.cast(self.__type + ' *', ffi.cast('void *', child) - ffi.offsetof(self.__type, self.__link))
		return self.__child_cls(ptr)


class SceneHelper(WlList):
	"Scene graph."
	
	def __init__(self, item: SceneTree | SceneRect | SceneBuffer):
		self.__item = item
		if self.type == SceneNodeType.TREE:
			WlList.__init__(self, ffi.addressof(self.__item._ptr.children), 'struct wlr_scene_node', 'link', self.__convert_child)
	
	def get_item(self) -> SceneTree | SceneRect | SceneBuffer:
		return self.__item
	
	@property
	def parent(self):
		return self.__class__(self.__item.node.parent)
	
	@property
	def x(self):
		return self.__node.x
	
	@x.setter
	def x(self, x):
		self.set_position(x, self.y)
	
	@property
	def y(self):
		return self.__node.y
	
	@y.setter
	def y(self, y):
		self.set_position(self.x, y)
	
	@property
	def width(self):
		return self.__node.width
	
	@width.setter
	def width(self, w):
		self.set_size(w, self.height)
	
	@property
	def height(self):
		return self.__node.height
	
	@height.setter
	def height(self, height):
		self.set_size(self.width, height)
	
	def __repr__(self):
		attrs = ['type', 'x', 'y']
		props = {'type':self.type.name, 'x':self.x, 'y':self.y}
		
		if self.type == SceneNodeType.RECT or self.type == SceneNodeType.BUFFER:
			attrs.extend(('width', 'height'))
			props['width'] = self.width
			props['height'] = self.height
		
		return self.__class__.__name__ + '(' + ', '.join(_key + '=' + repr(props[_key]) for _key in attrs) + ')' + (f'[{len(self)}]' if self.type == SceneNodeType.TREE else '')
	
	def __dir__(self):
		return list(frozenset().union(self.__dict__.keys(), dir(self.__item), dir(self.__item.node), dir(self.__item._ptr)))
	
	def __getattr__(self, attr):
		if hasattr(self.__item, attr):
			return getattr(self.__item, attr)
		elif hasattr(self.__item.node, attr):
			return getattr(self.__item.node, attr)
		elif hasattr(self.__item._ptr, attr):
			return getattr(self.__item._ptr, attr)
		else:
			raise AttributeError
	
	def __len__(self):
		if self.type != SceneNodeType.TREE:
			raise TypeError
		
		return WlList.__len__(self)
	
	def __getitem__(self, index):
		if self.type != SceneNodeType.TREE:
			raise TypeError
		
		return WlList.__getitem__(self, index)
	
	def __convert_child(self, ptr):
		scene_node = SceneNode(ptr)
		match scene_node.type:
			case SceneNodeType.RECT:
				r = object.__new__(SceneRect)
				r._ptr = ffi.cast('struct wlr_scene_rect *', ptr)
			case SceneNodeType.BUFFER:
				r = object.__new__(SceneBuffer)
				r._ptr = ffi.cast('struct wlr_scene_buffer *', ptr)
			case SceneNodeType.TREE:
				r = object.__new__(SceneTree)
				r._ptr = ffi.cast('struct wlr_scene_tree *', ptr)
			case _:
				raise NotImplementedError(str(scene_node.type.name))
		return self.__class__(r)
	
	def append_tree(self, x:int, y:int):
		tree = self.__class__(SceneTree.create(self.__item))
		tree.set_position(x, y)
		return tree
	
	def append_rect(self, x:int, y:int, width:int, height:int, color:tuple[float, float, float, float]):
		rect = self.__class__(SceneRect(self.__item, width, height, color))
		rect.set_position(x, y)
		return rect
	
	def append_buffer(self, x:int, y:int, buffer:Buffer):
		buff = self.__class__(SceneBuffer.create(self.__item, buffer))
		buff.set_position(x, y)
		return buff
	
	def append_surface(self, surface:XdgSurface):
		return self.__class__(Scene.xdg_surface_create(self.__item, surface))


def addr(object_):
	"If an object is a pointer, return the numeric value of that pointer. If it's an object that contains `_ptr` field, return the numeric value of that field."
	try:
		return int(ffi.cast('uintptr_t', object_._ptr))
	except AttributeError:
		return int(ffi.cast('uintptr_t', object_))


class Server:
	def __init__(self, log, cursor_size:int, seat_id:str, nested:bool):
		log.info(f"Creating server: cursor_size={cursor_size}, seat_id={seat_id}")
		self.log = log
		self.cursor_size = cursor_size
		self.seat_id = seat_id
		self.nested = nested
		
		self.reset()
	
	def reset(self):
		self.inputs = {} # Input devices: keyboards, mice and touch panels.
		self.outputs = {} # Output devices: monitors and offscreen buffers, also windows if it's a nested compositor.
		self.output_scene = {} # Scene tree to be displayed on a particular output.
		self.default_background_color = 0.05, 0.15, 0.2, 1 # Default background color will be drawn on all connected monitors. It will be visible only if there is no desktop manager.
		self.capabilities = 0 # Indicates whether the seat has certain input device.
		self.toplevels = {} # Toplevel surfaces.
		self.popups = {} # Popup surfaces.
		self.focused_surface = None # The toplevel currently in focus.
		self.pointed_surface = None # The surface currently under pointer.
	
	# How to treat missing handlers:
	# 0 - ignore; for production; also the fastest
	# 1 - notify; for development; slower
	# 2 - runtime error; raise error when missing handler is called; for debugging
	# 3 - static error; raise error when handler is not defined; to make sure all handler definitions are present
	missing_handlers = 1 if __debug__ else 0
	
	def __create_listener(self, object_name, event_name, event_fn, static_args=(), creation_object=None):
		name = (object_name + '_' if object_name else '') + event_name
		self.log.debug(f"Creating event handler: {name}")
		kwargs = {}
		if creation_object:
			kwargs['creation_object'] = creation_object
		listener = Listener(lambda listener, *args: event_fn(object_name, event_name, listener, *args, *static_args, **kwargs))
		listener.name = name
		return listener
	
	def install_events(self, parent_name, event_name, object_, static_args=()):
		assert event_name.startswith('new_') and event_name.endswith('_event')
		
		object_name = event_name[len('new_'):-len('_event')]
		if parent_name:
			parent_name += '_'
		
		for subevent_name in dir(object_):
			if not subevent_name.endswith('_event'): continue
			
			if (1 <= self.missing_handlers <= 2) or hasattr(self, parent_name + object_name + '_' + subevent_name) or subevent_name.startswith('destroy_'):
				if subevent_name.startswith('new_'):
					listener = self.__create_listener(parent_name + object_name, subevent_name, self.__event_create, static_args=static_args)
				elif subevent_name.startswith('destroy_'):
					listener = self.__create_listener(parent_name + object_name, subevent_name, self.__event_destroy, static_args=static_args, creation_object=object_)
				else:
					listener = self.__create_listener(parent_name + object_name, subevent_name, self.__event, static_args=static_args)
			elif self.missing_handlers == 0:
				self.log.debug(f"Ignoring event with undefined handler: {parent_name + object_name + '_' + subevent_name}")
				listener = None
			elif self.missing_handlers == 3:
				self.log.error(f"Ignoring event with undefined handler: {parent_name + object_name + '_' + subevent_name}")
				raise AttributeError(parent_name + object_name + '_' + subevent_name)
			else:
				raise ValueError
			
			if listener is not None:
				getattr(object_, subevent_name).add(listener)
	
	def __event_create(self, parent_name, event_name, listener, object_, *args):
		self.log.debug(f"Create event: {parent_name + '_' if parent_name else ''}{event_name}({', '.join([type(object_).__name__ + '@' + hex(addr(object_))] + [type(_arg).__name__ + '@' + hex(addr(_arg)) for _arg in args])})")
		self.install_events(parent_name, event_name, object_)
		
		if parent_name:
			parent_name += '_'
		
		try:
			handler = getattr(self, parent_name + event_name)
		except AttributeError:
			if self.missing_handlers == 1:
				self.log.warning(f"Unhandled event: {parent_name + event_name}")
			elif self.missing_handlers == 2:
				raise
			else:
				raise ValueError
		else:
			handler(object_, *args)
	
	def __event_destroy(self, parent_name, event_name, listener, object_, *args, creation_object=None):
		self.log.debug(f"Destroy event: {parent_name + '_' if parent_name else ''}{event_name}({', '.join([type(object_).__name__ + '@' + hex(addr(object_))] + [type(_arg).__name__ + '@' + hex(addr(_arg)) for _arg in args])})")
		assert event_name == 'destroy_event'
		assert creation_object
		
		if parent_name:
			parent_name += '_'
		
		try:
			handler = getattr(self, parent_name + event_name)
		except AttributeError:
			if self.missing_handlers == 0:
				pass
			elif self.missing_handlers == 1:
				self.log.warning(f"Unhandled event: {parent_name + event_name}")
			elif self.missing_handlers == 2:
				raise
			else:
				raise ValueError
		else:
			try:
				handler(object_, *args, creation_object=creation_object)
			except TypeError:
				handler(object_, *args)
	
	def __event(self, parent_name, event_name, listener, *args):
		self.log.debug(f"Event: {parent_name + '_' if parent_name else ''}{event_name}({', '.join([type(_arg).__name__ + '@' + hex(addr(_arg)) for _arg in args])})")
		assert event_name.endswith('_event')
		
		if parent_name:
			parent_name += '_'
		
		try:
			handler = getattr(self, parent_name + event_name)
		except AttributeError:
			if self.missing_handlers == 1:
				self.log.warning(f"Unhandled event: {parent_name + event_name}")
			elif self.missing_handlers == 2:
				raise
			else:
				raise ValueError
		else:
			handler(*args)
	
	def __enter__(self):
		"Create and initialize all session objects; install event listeners."
		
		self.log.info("Server context enter.")
		
		try:
			self.display = Display().__enter__() # Abstraction of the server itself.
			self.compositor, self.allocator, self.renderer, self.backend, self.subcompositor = build_compositor(self.display) # Managing graphics hardware.
			self.xdg_shell = XdgShell(self.display) # Shell assigning roles to app windows.
			self.output_layout = OutputLayout().__enter__() # Structure managing surfaces and monitors.
			self.cursor = Cursor(self.output_layout).__enter__() # Cursor sprite of the output layout.
			self.xcursor_manager = XCursorManager(None, self.cursor_size).__enter__() # Manager of X11-style cursor themes.
			self.xkb_context = xkb.Context() # Keyboard context to set keyboard layouts.
			self.seat = Seat(self.display, self.seat_id).__enter__() # Abstraction of user "seat" (input devices and monitors available to a single user).
			self.data_device_manager = DataDeviceManager(self.display) # Needed by Gtk apps.
			
			self.scene = Scene() # Scene tree of rectangular surfaces to display.
			self.scene_tree = SceneHelper(self.scene.tree) # Helper object to access scene tree.
			self.scene_output_layout = self.scene.attach_output_layout(self.output_layout) # Object that decides which surfaces to display on a particular monitor.
			
			self.idle_notify = IdleNotifierV1(self.display) # User idle notifier i.e. to be used by screensaver.
			self.layer_shell = LayerShellV1(self.display, 1) # Manager of desktop layers, so certain windows are rendered above others.
			self.foreign_manager = ForeignToplevelManagerV1(self.display._ptr) # Allows one app to export a surface to be consumed by another.
			self.decoration_manager = XdgDecorationManagerV1.create(self.display) # Decide whether clients draw their own decorations or not.
			self.decoration_manager_legacy = ServerDecorationManager.create(self.display) # Legacy decoration manager protocol, but Gtk supports it.
			
			#self.desktop_manager = DesktopManager()
			
			self.socket = self.display.add_socket() # Socket for communication with clients.
			self.event_loop = self.display.get_event_loop() # Event loop allowing assigning Unix signal handlers.
			
			# Automatically create event listeners if right methods are defined.
			for object_name in self.__wl_objects:
				if object_name in ['foreign_manager']: # Those managers cause problems.
					continue
				object_ = getattr(self, object_name)
				
				for event_name in dir(object_):
					if not event_name.endswith('_event'): continue
					
					if object_name == 'backend':
						effective_object_name = ''
						parent_object_name = ''
					else:
						effective_object_name = object_name + '_'
						parent_object_name = object_name
					
					if (1 <= self.missing_handlers <= 2) or hasattr(self, effective_object_name + event_name):
						if event_name.startswith('new_'):
							listener = self.__create_listener(parent_object_name, event_name, self.__event_create)
						elif event_name.startswith('destroy_'):
							listener = self.__create_listener(parent_object_name, event_name, self.__event_destroy, creation_object=object_)
						else:
							listener = self.__create_listener(parent_object_name, event_name, self.__event)
					elif self.missing_handlers == 0:
						self.log.debug(f"Event handler not defined: {effective_object_name + event_name}")
						listener = None
					elif self.missing_handlers == 3:
						self.log.error(f"Event handler not defined: {effective_object_name + event_name}")
						raise AttributeError(effective_object_name + event_name)
					else:
						raise ValueError
					
					if listener is not None:
						getattr(object_, event_name).add(listener)
			
			self.decoration_manager_legacy.set_default_mode(ServerDecorationManagerMode.SERVER) # Global setting: disable client-side decorations of Gtk apps.
			self.cursor.set_xcursor(self.xcursor_manager, 'left_ptr') # Global setting: default cursor.
			
			self.backend.__enter__() # Events start coming after this.
		
		except Exception as error:
			self.log.error("Error while constructing server.")
			self.log.error(f" {type(error).__name__}: {str(error)}")
			self.__exit__(type(error), error, None) # TODO: frame info
			raise
		
		if __debug__:
			for attr in self.__wl_objects:
				obj = getattr(self, attr)
				if attr in self.__managers:
					assert hasattr(obj, '__enter__') and hasattr(obj, '__exit__'), attr
				else:
					assert not hasattr(obj, '__enter__') and not hasattr(obj, '__exit__'), attr
		
		self.log.info("Server context enter success.")
		
		return self
	
	# objects are created in that order and destroyed in reverse order
	__wl_objects = [
		'event_loop', 'display', 'backend', 'compositor', 'allocator', 'renderer', 'subcompositor', 'data_device_manager',
		'xdg_shell', 'output_layout', 'cursor', 'xcursor_manager', 'seat', 'scene', 'scene_output_layout', 'idle_notify',
		'layer_shell', 'foreign_manager', 'xkb_context', 'decoration_manager', 'decoration_manager_legacy', 'socket'
	] # 'desktop_manager', 
	
	# objects that support context manager protocol
	__managers = {'output_layout', 'cursor', 'xcursor_manager', 'seat', 'backend', 'display'}
	
	def __exit__(self, exception_type, exception, traceback):
		"Destroy all session objects, explicitly finalizing them if needed."
		
		self.log.info("Server context exit.")
		
		if exception:
			self.log.error(str(exception))
				
		del self.scene_tree # Must be deleted before self.scene.
		
		for attr in reversed(self.__wl_objects):
			if attr == 'event_loop': continue
			
			try:
				if hasattr(self, attr):
					if attr in self.__managers:
						getattr(self, attr).__exit__(None, None, None)
					else:
						try:
							getattr(self, attr).destroy()
						except AttributeError:
							pass
					delattr(self, attr)
			except Exception as error:
				self.log.error(str(error))
		
		self.reset()
		
		self.log.info("Server context exit success.")
	
	def new_input_event(self, input_device:InputDevice):
		"Prepare a new input device (like a keyboard or a pointer) to use."
		assert isinstance(input_device, InputDevice)
		self.log.info(f"Attached new {input_device.type.name.lower()} input device: {input_device.name}")
		
		match input_device.type:
			case InputDeviceType.KEYBOARD:
				keyboard = Keyboard.from_input_device(input_device)
				self.inputs[addr(input_device)] = keyboard
				self.install_events('', 'new_keyboard_event', keyboard, static_args=(keyboard,))
				self.new_keyboard_event(keyboard)
			case InputDeviceType.POINTER:
				pointer = Pointer.from_input_device(input_device)
				self.inputs[addr(input_device)] = pointer
				self.install_events('', 'new_pointer_event', pointer, static_args=(pointer,))
				self.new_pointer_event(pointer)
			case InputDeviceType.TOUCH:
				touch = Touch.from_input_device(input_device)
				self.inputs[addr(input_device)] = touch
				self.install_events('', 'new_touch_event', touch, static_args=(touch,))
				self.new_touch_event(touch)
			case _:
				self.log.warning("Unsupported input device type.")
	
	def input_destroy_event(self, input_ptr):
		"Input device destroy event."
		self.log.info(f"Detached {self.inputs[addr(input_ptr)].base.type.name.lower()} input device {self.inputs[addr(input_ptr)].base.name}")
		
		input_device = self.inputs[addr(input_ptr)]
		del self.inputs[addr(input_ptr)]
		
		match input_device.base.type:
			case InputDeviceType.KEYBOARD:
				self.keyboard_destroy_event(input_device)
			case InputDeviceType.POINTER:
				self.pointer_destroy_event(input_device)
			case InputDeviceType.TOUCH:
				self.touch_destroy_event(input_device)
			case _:
				self.log.warning("Unsupported input device type.")
	
	def new_keyboard_event(self, keyboard:Keyboard):
		"New keyboard attached."
		keymap = self.xkb_context.keymap_new_from_names()
		self.log.debug(f" keyboard {keyboard.base.name} {keymap.layout_get_name(0)}")
		keyboard.set_keymap(keymap)
		keyboard.set_repeat_info(25, 350)
		
		if not (self.capabilities & WlSeat.capability.keyboard):
			self.capabilities |= WlSeat.capability.keyboard
			self.seat.set_capabilities(self.capabilities)
	
	def keyboard_modifiers_event(self, event, keyboard:Keyboard):
		"Modifier key has been pressed / released."
		self.log.debug(f"keyboard modifiers {event} {keyboard}")
		self.idle_notify.notify_activity(self.seat)
		self.seat.set_keyboard(keyboard)
		self.seat.keyboard_notify_modifiers(keyboard.modifiers)
	
	def keyboard_key_event(self, event:KeyboardKeyEvent, keyboard:Keyboard):
		"A key has been pressed / released."
		if not hasattr(self, 'idle_notify'):
			"If the compositor has been closed using key combination, abort sequence; else the key release events would be triggered on finished object."
			return
		self.log.debug(f"keyboard key {event} {keyboard}")
		self.idle_notify.notify_activity(self.seat)
		self.seat.set_keyboard(keyboard)
		self.seat.keyboard_notify_key(event)
	
	def keyboard_destroy_event(self, keyboard:Keyboard):
		"Keyboard detached."
		if hasattr(self, 'seat'): # Check if the seat lost any capability.
			capabilities = self.capabilities
			
			if not any(_input_device.base.type == InputDeviceType.KEYBOARD for _input_device in self.inputs.values()):
				capabilities &= ~WlSeat.capability.keyboard
			
			if capabilities != self.capabilities:
				self.seat.set_capabilities(capabilities)
	
	def new_pointer_event(self, pointer:Pointer):
		"New pointer (mouse, trackball) attached."
		self.log.debug(f" pointer {pointer.base.name} on screen {pointer.output_name}")
		
		self.cursor.attach_input_device(pointer.base)
		
		if not (self.capabilities & WlSeat.capability.pointer):
			self.capabilities |= WlSeat.capability.pointer
			self.seat.set_capabilities(self.capabilities)
	
	def pointer_destroy_event(self, pointer:Pointer):
		"Pointer detached."
		if hasattr(self, 'cursor'):
			self.cursor.detach_input_device(pointer.base)
		
		if hasattr(self, 'seat'): # Check if the seat lost any capability.
			capabilities = self.capabilities
			
			if not any(_input_device.base.type == InputDeviceType.POINTER for _input_device in self.inputs.values()):
				capabilities &= ~WlSeat.capability.pointer
			
			if capabilities != self.capabilities:
				self.seat.set_capabilities(capabilities)
	
	def new_touch_event(self, touch:Touch):
		"New touchscreen, touch panel or graphic tablet attached."
		self.log.debug(f" touch {touch.base.name} {touch.width_mm}mm × {touch.height_mm}mm")
		
		if not (self.capabilities & WlSeat.capability.touch):
			self.capabilities |= WlSeat.capability.touch
			self.seat.set_capabilities(self.capabilities)
	
	def touch_destroy_event(self, touch:Touch):
		"Touchscreen detached."
		if hasattr(self, 'seat'): # Check if the seat lost any capability.
			capabilities = self.capabilities
			
			if not any(_input_device.base.type == InputDeviceType.TOUCH for _input_device in self.inputs.values()):
				capabilities &= ~WlSeat.capability.touch
			
			if capabilities != self.capabilities:
				self.seat.set_capabilities(capabilities)
	
	def cursor_motion_absolute_event(self, event:PointerMotionAbsoluteEvent):
		"Absolute cursor motion event. Argument contains `x` and `y` fields."
		
		pointer = event.pointer
		self.cursor.warp(WarpMode.AbsoluteClosest, event.x, event.y, input_device=pointer.base)
		self.idle_notify.notify_activity(self.seat)
		
		pointed_surface, x, y = self.pointed()
		if (bool(pointed_surface) != bool(self.pointed_surface)) or (pointed_surface and self.pointed_surface and addr(pointed_surface) != addr(self.pointed_surface)):
			self.pointed_surface = pointed_surface
			if pointed_surface:
				self.seat.pointer_notify_enter(pointed_surface, x, y)
			else:
				self.seat.pointer_clear_focus()
		
		if pointed_surface:
			self.log.debug(f"Cursor motion event inside {hex(addr(pointed_surface))}: {x, y}")
			self.seat.pointer_notify_motion(event.time_msec, x, y)
	
	def cursor_motion_event(self, event:PointerMotionEvent):
		"Relative cursor motion event. Argument contains `delta_x` and `delta_y` fields."
		
		pointer = event.pointer
		self.cursor.move(event.delta_x, event.delta_y, input_device=pointer.base)
		self.idle_notify.notify_activity(self.seat)
		
		pointed_surface, x, y = self.pointed()
		if (bool(pointed_surface) != bool(self.pointed_surface)) or (pointed_surface and self.pointed_surface and addr(pointed_surface) != addr(self.pointed_surface)):
			self.pointed_surface = pointed_surface
			if pointed_surface:
				self.seat.pointer_notify_enter(pointed_surface, x, y)
			else:
				self.seat.pointer_clear_focus()
		
		if pointed_surface:
			self.log.debug(f"Cursor motion event inside {hex(addr(pointed_surface))}: {x, y}")
			self.seat.pointer_notify_motion(event.time_msec, x, y)
	
	def cursor_button_event(self, event:PointerButtonEvent):
		"Mouse button click."
		self.log.debug(f"cursor button event: {self.cursor.x}, {self.cursor.y}, {event.button}, {event.button_state}")
		self.idle_notify.notify_activity(self.seat)
		if self.pointed_surface:
			self.seat.pointer_notify_button(event.time_msec, event.button, event.button_state)
	
	def cursor_axis_event(self, event):
		"Mouse wheel roll."
		self.idle_notify.notify_activity(self.seat)
		if self.pointed_surface:
			self.seat.pointer_notify_axis(event.time_msec, event.orientation, event.delta, event.delta_discrete, event.source)
	
	def cursor_frame_event(self, event):
		self.seat.pointer_notify_frame()
	
	def new_output_event(self, output_device:Output):
		"Prepare a new output device (i.e. monitor or an offscreen buffer) to use."
		assert isinstance(output_device, Output)
		self.log.info(f"New output device attached: {output_device.name}")
		
		self.outputs[addr(output_device)] = output_device
		
		output_device.init_render(self.allocator, self.renderer)
		output_device.enable()
		
		# Create a default solid background on a newly attached screen. It is visible only if window manager is down.
		box = self.output_layout.get_box(output_device)
		background = self.scene_tree.append_tree(box.x, box.y)
		background.append_rect(0, 0, box.width, box.height, self.default_background_color)
		background.append_tree(0, 0)
		self.output_scene[addr(output_device)] = background
		
		self.scene_output_layout.add_output(self.output_layout.add_auto(output_device), SceneOutput.create(self.scene, output_device)) # Add the output to scene output layout.
		
		output_device.commit() # Start delivering frames.
	
	def output_frame_event(self, output_addr):
		"Render a frame by painting a scene graph output."
		try:
			output_device = self.outputs[addr(output_addr)]
		except KeyError: # Output device may be missing from the list during cleanup.
			return
		
		# Manual rendering. Compositor may draw anything.
		#output_device.attach_render() # Grab GPU so it draws for this particular monitor.
		#self.renderer.begin(*output_device.effective_resolution())
		#self.renderer.clear(self.default_background_color)
		#output_device.render_software_cursors()
		#self.renderer.end()
		#output_device.commit()
		
		# Render the scene. Windows will be drawn.
		scene_output = self.scene.get_scene_output(output_device)
		assert scene_output._ptr, f"Output {output_device.name} hasn't been added to scene output layout."
		scene_output.commit()
		scene_output.send_frame_done(Timespec.get_monotonic_time())
	
	def output_request_state_event(self, event):
		"This event is called when an output device changes state, like switches resolution."
		output_device = event.output
		if addr(output_device) not in self.outputs:
			return
		state = event.state
		
		self.log.info(f"Output device {output_device.name} changed mode to: {state.custom_mode}")
				
		if state.custom_mode:
			output_device.set_custom_mode(state.custom_mode)
		output_device.commit()
	
	def output_layout_change_event(self, layout_ptr):
		"Layout changed, probably because an output changed resolution."
		
		# build mapping background -> window
		toplevel_per_output = defaultdict(list)
		for toplevel in self.toplevels.values():
			toplevel_per_output[addr(toplevel.data.parent.parent)].append(toplevel)
		
		for output_device in self.outputs.values():
			box = self.output_layout.get_box(output_device)
			background = self.output_scene[addr(output_device)]
			background.set_position(box.x, box.y)
			background[0].set_size(box.width, box.height) # resize background color rectangle
			for toplevel in toplevel_per_output[addr(background)]:
				toplevel.set_size(box.width, box.height) # resize each window on this output
	
	def output_destroy_event(self, output_device_ptr):
		"Output device destroy event. Monitor was disconnected or window closed."
		
		self.log.info(f"Output device detached: {self.outputs[addr(output_device_ptr)].name}")
		
		# TODO: remap all surfaces to another output
		output_device = self.outputs[addr(output_device_ptr)]
		if not hasattr(self, 'output_layout'): return
		self.output_layout.remove(output_device)
		
		background = self.output_scene[addr(output_device_ptr)]
		background.destroy() # Destroy background.
		del self.outputs[addr(output_device_ptr)], self.output_scene[addr(output_device_ptr)]
		
		# For a nested compositor, exit when the last window is closed.
		# For a root compositor it makes sense to keep running as a new monitor may be attached.
		if self.nested and not self.outputs:
			self.close()
	
	def seat_request_set_cursor_event(self, event):
		"A client provides its own cursor image."
		self.log.debug("seat request set cursor")
		self.cursor.set_surface(event.surface, event.hotspot)
	
	def seat_request_set_selection_event(self, event:RequestSetSelectionEvent):
		self.log.debug("seat request set selection")
		self.seat.set_selection(event._ptr.source, event.serial)
	
	def xdg_shell_new_surface_event(self, xdg_surface:XdgSurface):
		"New XdgSurface (like an app window), toplevel or popup, from xdg_shell protocol."
		
		self.log.debug("New xdg surface {hex(addr(xdg_surface))}.")
		
		if xdg_surface.role == XdgSurfaceRole.TOPLEVEL:
			self.toplevels[addr(xdg_surface)] = xdg_surface
			self.install_events('toplevel', 'new_surface_event', xdg_surface.toplevel, static_args=(xdg_surface,))
			self.install_events('toplevel', 'new_surface_event', xdg_surface.surface, static_args=(xdg_surface,))
			self.new_toplevel_surface_event(xdg_surface)
		elif  xdg_surface.role == XdgSurfaceRole.POPUP:
			self.popups[addr(xdg_surface)] = xdg_surface
			self.install_events('popup', 'new_surface_event', xdg_surface.popup, static_args=(xdg_surface,))
			self.install_events('popup', 'new_surface_event', xdg_surface.surface, static_args=(xdg_surface,))
			self.new_popup_surface_event(xdg_surface)
		else:
			raise ValueError
	
	def xdg_shell_surface_destroy_event(self, null, creation_object=None):
		"This event is called when any XdgSurface is destroyed. The argument is always a null pointer apparently."
		
		xdg_surface = creation_object
		self.log.debug("Destroy xdg surface {hex(addr(xdg_surface))}")
		
		if xdg_surface.role == XdgSurfaceRole.TOPLEVEL:
			del self.toplevels[addr(xdg_surface)]
		elif xdg_surface.role == XdgSurfaceRole.POPUP:
			del self.popups[addr(xdg_surface)]
		else:
			raise ValueError
	
	def new_toplevel_surface_event(self, xdg_surface):
		"New toplevel window."
		self.log.info(f"New toplevel surface: {xdg_surface.toplevel.app_id}")
		output = list(self.outputs.values())[0] # TODO: select output
		xdg_surface.data = self.output_scene[addr(output)][1].append_surface(xdg_surface) # Create scene node and assign to the `data` field.
		box = self.output_layout.get_box(output)
		
		xdg_surface.set_size(box.width, box.height) # Resize the window to take all screen.
		xdg_surface.set_fullscreen(True) # Notify the window that it's in fullscreen mode (may affect content).
		xdg_surface.set_resizing(False) # Forbid manual window resizing.
		xdg_surface.set_tiled(True) # Inform the window that it's a "tiling" window manager.
	
	def toplevel_surface_map_event(self, null, xdg_surface):
		"Show toplevel window."
		self.log.info(f"Map toplevel surface: {xdg_surface.toplevel.app_id}")
		
		self.focus(xdg_surface) # Focus the newly mapped surface.
		pointed_surface, x, y = self.pointed()
		if (bool(pointed_surface) != bool(self.pointed_surface)) or (pointed_surface and self.pointed_surface and addr(pointed_surface) != addr(self.pointed_surface)):
			self.pointed_surface = pointed_surface
			if pointed_surface:
				print(f"cursor {x, y}")
				self.seat.pointer_notify_enter(pointed_surface, x, y)
		
		for output in self.outputs.values():
			output.commit()
	
	def toplevel_surface_unmap_event(self, null, xdg_surface):
		"Hide toplevel window."
		self.log.info(f"Unmap toplevel surface: {xdg_surface.toplevel.app_id}")
		self.focus(None) # Unfocus.
		for output in self.outputs.values():
			output.commit()
	
	def toplevel_surface_destroy_event(self, null, xdg_surface, creation_object=None):
		"Destroy toplevel window."
		self.log.info(f"Destroy toplevel surface: {hex(addr(xdg_surface))}")
		
		assert creation_object
		surface = creation_object
	
	def new_popup_surface_event(self, xdg_surface):
		"New popup window."
		popup = xdg_surface.popup
		xdg_surface.data = XdgSurface.from_surface(popup.parent).data.append_surface(xdg_surface) # Find parent; find scene node from parent's `data` field; create new scene node; assign to popup's `data` field.
		
		toplevel = XdgSurface.from_surface(popup.parent)
		if self.focused_surface and addr(toplevel) == addr(self.focused_surface):
			self.focus(popup) # give the popup focus but only if its parent already had one
	
	def popup_surface_destroy_event(self, null, xdg_surface, creation_object=None):
		"Destroy popup window."
		self.log.info(f"Destroy popup surface: {hex(addr(xdg_surface))}")
		
		assert creation_object
		surface = creation_object
		
		toplevel = XdgSurface.from_surface(popup.parent)
		if self.focused_surface and addr(toplevel) == addr(self.focused_surface):
			self.focus(toplevel) # give focus back to parent
	
	def decoration_manager_new_toplevel_decoration_event(self, decoration:XdgToplevelDecorationV1):
		"Per-window decoration manager."
		self.log.debug("Disable client-side window decorations.")
		decoration.set_mode(XdgToplevelDecorationV1Mode.SERVER_SIDE) # Disable client-side decorations for the newly created window that supports this protocol.
	
	def destroy_event(self, backend_ptr):
		"Server destroy event; the last to be called."
		self.log.debug("Backend destroyed.")
	
	def run(self):
		"Run the server (main loop)."
		self.display.run()
	
	def close(self):
		"Gracefully close the server. This function should be overrided to kill the session."
		print(type(self.xdg_shell.new_surface_event))
		self.display.terminate()
	
	def pointed(self):
		"Return the surface currently under cursor (may be None) and pointer coordinates inside that surface."
		
		pointed_surface = None
		x = y = 0
		
		node_x_y = self.scene.tree.node.node_at(self.cursor.x, self.cursor.y)
		if node_x_y is not None:
			node, x, y = node_x_y
			
			if node.type == SceneNodeType.BUFFER:
				scene_buffer = SceneBuffer.from_node(node)
				if scene_buffer is not None:
					scene_surface = SceneSurface.from_buffer(scene_buffer)
					if scene_surface is not None:
						pointed_surface = scene_surface.surface
		
		return pointed_surface, x, y
	
	def focus(self, xdg_surface):
		"Focus the surface (may be None)."
		
		if xdg_surface is None:
			if self.focused_surface:
				self.focused_surface.set_activated(False) # notify the previously focused window it's been disactivated (may affect content)
				self.focused_surface = None
			self.seat.pointer_clear_focus() # tell seat no windows are in focus
		
		elif xdg_surface.role == XdgSurfaceRole.TOPLEVEL:
			toplevel = xdg_surface
			
			if not self.focused_surface or addr(toplevel) != addr(self.focused_surface):
				if self.focused_surface:
					self.focused_surface.set_activated(False) # notify the previously focused window it's been disactivated (may affect content)
					self.log.info(f"disactivated window: {hex(addr(self.focused_surface))}")
				self.focused_surface = toplevel
				toplevel.data.raise_to_top() # raise the window to the top of the deck
				toplevel.set_activated(True) # notify the window it's been activated (may affect content)
				self.log.info(f"activated window: {hex(addr(toplevel))}")
			
			for keyboard in self.inputs.values(): # give the window keyboard focus of all attached keyboards
				if not keyboard.base.type == InputDeviceType.KEYBOARD: continue
				server.seat.keyboard_notify_enter(toplevel.surface, keyboard)
			self.log.info(f"keyboard focus to toplevel: {hex(addr(toplevel))}")
		
		elif xdg_surface.role == XdgSurfaceRole.POPUP:
			popup = xdg_surface
			toplevel = XdgSurface.from_surface(popup.parent)
			
			if not self.focused_surface or addr(toplevel) != addr(self.focused_surface):
				if self.focused_surface:
					self.focused_surface.set_activated(False) # notify the previously focused window it's been disactivated (may affect content)
					self.log.info(f"disactivated window: {hex(addr(self.focused_surface))}")
				self.focused_surface = toplevel
				toplevel.data.raise_to_top() # raise the parent window to the top of the deck
				toplevel.set_activated(True) # notify the parent window it's been activated (may affect content)
				self.log.info(f"activated window: {hex(addr(toplevel))}")
			
			for keyboard in self.inputs.values(): # give the popup keyboard focus of all attached keyboards
				if not keyboard.base.type == InputDeviceType.KEYBOARD: continue
				server.seat.keyboard_notify_enter(popup.surface, keyboard)
			self.log.info(f"keyboard focus to popup: {hex(addr(popup))}")
		
		else:
			raise ValueError


if __name__ == '__main__':
	logger.info("Gwayco - Wayland composer delegating window positioning to Gtk.")
	logger.info(f"  gwayco version: {__version__} ({__status__})")
	logger.info(f" wlroots version: {wlroots_version.version}")
	
	import os, signal
	from subprocess import Popen, PIPE, TimeoutExpired
	
	if len(sys.argv) < option_args_n + 1:
		logger.error(f"Usage: {sys.argv[0]} [--gwayco-LOGLEVEL] [--wlroots-LOGLEVEL] <session command> <args ...>")
		logger.error( "       LOGLEVEL = debug | infos | warnings | errors | silent")
		
		if __debug__:
			logger.info("")
			logger.info(f"Try: {sys.argv[0]} ./hello.py hello, void")
			logger.info(f"     {sys.argv[0]} ./kittens.py")
			logger.info(f"     {sys.argv[0]} ./gwayco-session.py")
		exit(1)
	
	try:
		seat_id = os.environ['XDG_SEAT']
	except KeyError:
		logger.error("Export XDG_SEAT environment variable, i.e. 'seat0'.")
		exit(1)
	
	session_cmd = sys.argv[option_args_n:]
	
	with Server(log=logger, cursor_size=24, seat_id=seat_id, nested=True) as server:
		server.event_loop.add_signal(signal.SIGINT, lambda signum, _: server.close()) # Close on SIGTERM.
		
		server.log.info("Starting session")
		
		environ = os.environ.copy() # Create session environment.
		if 'DISPLAY' in environ: # Delete DISPLAY lest the clients connect to X11.
			del environ['DISPLAY']
		environ['GDK_BACKEND'] = 'wayland' # Inform Gtk apps to connect to Wayland.
		environ['QT_WAYLAND_DISABLE_WINDOWDECORATION'] = '1'
		environ['LD_PRELOAD'] = 'libgtk3-nocsd.so.0'
		environ['WAYLAND_DISPLAY'] = server.socket.decode() # Wayland socket name.
		server.log.info(f"Wayland server listening on socket {server.socket.decode()}")
		
		session = Popen(session_cmd, shell=False, env=environ) # Spawn the session process. The child inherits the terminal, so ctrl+C will be received by it.
		close = server.close
		server.close = lambda: session.terminate() # Override `close` method to kill the session process.
		server.event_loop.add_signal(signal.SIGCHLD, lambda signum, _: close() if session.poll() is not None else None) # Close server when session process ended.
		
		server.log.info("Session started")
		
		server.run() # Main loop.
		
		server.log.info("Finishing session")
		try:
			session.wait(timeout=3) # Collect the session process result.
		except TimeoutExpired:
			logger.error("Timeout waiting for session to exit.")
			session.kill() # Kill the session if it didn't die soon enough.
		server.log.info("Session finished")
	
	logger.info("Bye")

