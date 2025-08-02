#!/usr/bin/python3


import logging
loglevel = logging.DEBUG
logging.basicConfig(level=loglevel)

from wlroots.util.log import log_init
log_init(loglevel)

from wlroots import ffi
from wlroots.helper import build_compositor
from wlroots.wlr_types import Cursor, DataDeviceManager, OutputLayout, Scene, Seat, XCursorManager, XdgShell, InputDevice, Output, Keyboard, SceneNodeType, SceneSurface, SceneBuffer, Buffer

from wlroots.wlr_types.idle_notify_v1 import IdleNotifierV1
from wlroots.wlr_types.layer_shell_v1 import LayerShellV1, LayerSurfaceV1
from wlroots.wlr_types.foreign_toplevel_management_v1 import ForeignToplevelManagerV1
from wlroots.wlr_types.xdg_decoration_v1 import XdgDecorationManagerV1, XdgToplevelDecorationV1

from wlroots.wlr_types.scene import SceneNode, SceneRect, SceneBuffer, SceneTree
from wlroots.wlr_types.cursor import WarpMode
from wlroots.wlr_types.input_device import ButtonState, InputDeviceType
from wlroots.wlr_types.keyboard import KeyboardModifier, KeyboardKeyEvent
from wlroots.wlr_types.pointer import PointerButtonEvent, PointerMotionAbsoluteEvent, PointerMotionEvent
from wlroots.wlr_types.seat import RequestSetSelectionEvent
from wlroots.wlr_types.xdg_shell import XdgSurface, XdgSurfaceRole
from wlroots.util.clock import Timespec

from pywayland.server import Display, Client, Listener
from pywayland.protocol.wayland import WlKeyboard, WlSeat
from xkbcommon import xkb

from itertools import product


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


class DesktopManager:
	class Record:
		pass
	
	def __init__(self):
		self.desktop = {}
		self.windows = {}
	
	def create_desktop(self, output):
		desktop = self.desktop[int(ffi.cast('uintptr_t', output._ptr))] = self.Record()
		desktop.windows = {}
		desktop.positions = {}
		desktop.shown = {}
		desktop.order = []
		desktop.width = 0
		desktop.height = 0
		self.__reposition(desktop)
		self.__commit(desktop)
	
	def destroy_desktop(self, output):
		del self.desktop[int(ffi.cast('uintptr_t', output._ptr))]
		for w_id in [w_id for w_id, d_id in self.windows.items() if d_id == int(ffi.cast('uintptr_t', output._ptr))]:
			del self.windows[w_id]
	
	def resize_desktop(self, output, w, h):
		desktop = self.desktop[int(ffi.cast('uintptr_t', output._ptr))]
		desktop.width = w
		desktop.height = h
		self.__reposition(desktop)
		self.__commit(desktop)
	
	def create_window(self, output, surface):
		print("create_window", surface.toplevel.app_id, surface.toplevel.title, surface.toplevel.parent)
		self.windows[id(surface)] = int(ffi.cast('uintptr_t', output._ptr))
		desktop = self.desktop[int(ffi.cast('uintptr_t', output._ptr))]
		desktop.order.append(id(surface))
		desktop.windows[id(surface)] = surface
		desktop.shown[id(surface)] = False
		self.__reposition(desktop)
		self.__commit(desktop)
	
	def destroy_window(self, surface):
		desktop = self.desktop[self.windows[id(surface)]]
		desktop.order.remove(id(surface))
		del desktop.windows[id(surface)]
		del desktop.positions[id(surface)]
		del desktop.shown[id(surface)]
		self.__reposition(desktop)
		self.__commit(desktop)
	
	def update_window(self, surface):
		print("update_window", surface.toplevel.app_id, surface.toplevel.title, surface.toplevel.parent)
		desktop = self.desktop[self.windows[id(surface)]]
		self.__reposition(desktop)
		self.__commit(desktop)
	
	def map_window(self, surface):
		desktop = self.desktop[self.windows[id(surface)]]
		desktop.shown[id(surface)] = True
		self.__reposition(desktop)
		self.__commit(desktop)
	
	def unmap_window(self, surface):
		desktop = self.desktop[self.windows[id(surface)]]
		desktop.shown[id(surface)] = False
		self.__reposition(desktop)
		self.__commit(desktop)
	
	def __reposition(self, desktop):
		assert isinstance(desktop, self.Record)
		desktop.order.sort(key=lambda _id: str(desktop.windows[_id].toplevel.app_id))
		order = [_v for _v in desktop.order if desktop.shown[_v]]
		max_columns = 4
		rows = (len(order) - 1) // max_columns + 1
		columns = min(len(order), max_columns)
		
		for id_, (j, i) in zip(order, product(range(rows), range(columns))):
			print(id_, (i, j), '/', (columns, rows))
			desktop.positions[id_] = int(i * desktop.width / columns), int(j * desktop.height / rows), int(desktop.width / columns), int(desktop.height / rows)
	
	def __commit(self, desktop):
		assert isinstance(desktop, self.Record)
		order = [_v for _v in desktop.order if desktop.shown[_v]]
		for id_ in order:
			surface = desktop.windows[id_]
			x, y, w, h = desktop.positions[id_]
			surface.data.set_position(x, y)
			surface.set_size(w, h)


class Server:
	def __init__(self, log, cursor_size:int, seat_id:str):
		log.info("Creating server: cursor_size={cursor_size}, seat_id={seat_id}")
		self.log = log
		self.cursor_size = cursor_size
		self.seat_id = seat_id
		self.__reset()
	
	def __reset(self):
		self.notification_serial = 0
		
		self.manager_in = None
		self.manager_out = None
		
		self.scene_node = {}
		
		self.focused_surface = None
		self.pointed_surface = None
		
		self.keyboards = []
		self.surfaces = {}
		self.outputs = {}
		self.output_background = {}
		self.default_background_color = 0, 0, 0.4, 1
	
	def __enter__(self):
		"Create and initialize all session objects; install event listeners."
		
		self.log.info("Server context enter.")
		
		try:
			self.display = Display().__enter__()
			self.compositor, self.allocator, self.renderer, self.backend, self.subcompositor = build_compositor(self.display)
			self.device_manager = DataDeviceManager(self.display)
			self.xdg_shell = XdgShell(self.display)
			self.desktop_manager = DesktopManager()
			self.output_layout = OutputLayout().__enter__()
			self.cursor = Cursor(self.output_layout).__enter__()
			self.xcursor_manager = XCursorManager(None, self.cursor_size).__enter__()
			self.seat = Seat(self.display, self.seat_id).__enter__()
			
			self.scene = Scene()
			self.scene.attach_output_layout(self.output_layout)
			self.scene_tree = SceneHelper(self.scene.tree)
			
			self.idle_notify = IdleNotifierV1(self.display)
			self.layer_shell = LayerShellV1(self.display, 1)
			self.foreign_manager = ForeignToplevelManagerV1(self.display._ptr)
			self.xkb_context = xkb.Context()
			self.decoration_manager = XdgDecorationManagerV1(self.display._ptr)
			
			self.xdg_shell.new_surface_event.add(Listener(self.new_surface))
			self.layer_shell.new_surface_event.add(Listener(self.new_surface_layer))
			self.decoration_manager.new_toplevel_decoration_event.add(Listener(self.new_toplevel_decoration))
			self.backend.new_input_event.add(Listener(self.new_input))
			self.backend.new_output_event.add(Listener(self.new_output))
			self.cursor.motion_event.add(Listener(self.cursor_motion))
			self.cursor.motion_absolute_event.add(Listener(self.cursor_motion_absolute))
			self.cursor.button_event.add(Listener(self.cursor_button))
			self.cursor.axis_event.add(Listener(self.cursor_axis))
			self.cursor.frame_event.add(Listener(self.cursor_frame))
			self.seat.request_set_cursor_event.add(Listener(self.request_set_cursor))
			self.seat.request_set_selection_event.add(Listener(self.request_set_selection))
			
			self.socket = self.display.add_socket()
			self.backend.__enter__()
			self.event_loop = self.display.get_event_loop()
		except Exception as error:
			self.log.error("Error while constructing server.")
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
		'display', 'compositor', 'allocator', 'renderer', 'backend', 'subcompositor', 'device_manager',
		'xdg_shell', 'desktop_manager', 'output_layout', 'cursor', 'xcursor_manager', 'seat', 'scene', 'idle_notify',
		'layer_shell', 'foreign_manager', 'xkb_context', 'decoration_manager', 'socket', 'event_loop'
	]
	
	# objects that support context manager protocol
	__managers = frozenset(['display', 'output_layout', 'cursor', 'xcursor_manager', 'seat', 'backend'])
	
	def __exit__(self, exception_type, exception, traceback):
		"Destroy all session objects, explicitly finalizing them if needed."
		
		self.log.info("Server context exit.")
		
		if exception:
			self.log.error(str(exception))
		
		self.manager_in = self.manager_out = None
		
		for attr in reversed(self.__wl_objects):
			self.log.debug(f"delete {attr}")
			try:
				if hasattr(self, attr):
					if attr in self.__managers:
						getattr(self, attr).__exit__(None, None, None)
					delattr(self, attr)
			except Exception as error:
				self.log.error(str(error))
		
		self.__reset()
		
		self.log.info("Server context exit success.")
	
	def new_surface_layer(self, listener, surface:LayerSurfaceV1):
		self.log.info(f"new wlr layer surface {surface}")
		print(dir(surface))
		for state in [surface.current, surface.pending]:
			print("anchor:", *[_label for _label, _if in zip(['top', 'bottom', 'left', 'right'], [(state.anchor >> _n) & 1 for _n in range(4)]) if _if])
			print("layer:", ['background', 'bottom', 'top', 'overlay'][state.layer])
			print("actual size:", state.actual_width, state.actual_height, "desired size:", state.desired_width, state.desired_height)
	
	def new_toplevel_decoration(self, listener, decoration:XdgToplevelDecorationV1):
		self.log.info(f"new toplevel decoration {decoration}")
		print(dir(decoration))
	
	def new_surface(self, listener, surface:XdgSurface):
		"New surface was created by a client; add it to scene graph and install event listeners."
		
		self.log.info(f"new xdg surface {surface.role.name}")
		
		surface.destroy_event.add(Listener(lambda listener, event: self.surface_destroy(listener, event, surface)))
		surface.map_event.add(Listener(lambda listener, event: self.surface_map(listener, event, surface)))
		surface.unmap_event.add(Listener(lambda listener, event: self.desktop_manager.unmap_window(surface) if surface.role == XdgSurfaceRole.TOPLEVEL else None))
		#surface.new_popup_event.add(Listener(lambda listener, event: self.surface_new_popup(listener, event, surface)))
		#surface.configure_event.add(Listener(lambda listener, event: self.surface_configure(listener, event, surface)))
		#surface.ack_configure_event.add(Listener(lambda listener, event: self.surface_ack_configure(listener, event, surface)))
		
		if surface.role == XdgSurfaceRole.TOPLEVEL:
			toplevel = surface.toplevel
			
			self.log.info(f" toplevel id='{toplevel.app_id}' title='{toplevel.title}' parent={toplevel.parent}")
			
			#toplevel.request_move_event.add(Listener(lambda listener, event: self.manager_notify('move', 'TOPLEVEL', event, surface)))
			#toplevel.request_resize_event.add(Listener(lambda listener, event: self.manager_notify('resize', 'TOPLEVEL', event, surface)))
			#toplevel.request_maximize_event.add(Listener(lambda listener, event: self.manager_notify('maximize', 'TOPLEVEL', event, surface)))
			#toplevel.request_minimize_event.add(Listener(lambda listener, event: self.manager_notify('minimize', 'TOPLEVEL', event, surface)))
			#toplevel.request_fullscreen_event.add(Listener(lambda listener, event: self.manager_notify('fullscreen', 'TOPLEVEL', event, surface)))
			#toplevel.request_show_window_menu_event.add(Listener(lambda listener, event: self.manager_notify('show_window_menu', 'TOPLEVEL', event, surface)))
			toplevel.set_parent_event.add(Listener(lambda listener, event: self.toplevel_update(listener, event, surface)))
			toplevel.set_title_event.add(Listener(lambda listener, event: self.toplevel_update(listener, event, surface)))
			toplevel.set_app_id_event.add(Listener(lambda listener, event: self.toplevel_update(listener, event, surface)))
			
			output = list(self.outputs.values())[0] # TODO: select output
			surface.data = self.output_background[int(ffi.cast('uintptr_t', output._ptr))][1].append_surface(surface) # create scene node and assign to the `data` field
			
			if surface.toplevel.app_id not in self.desktop_manager.desktop:
				self.desktop_manager.create_window(output, surface)
		
		elif surface.role == XdgSurfaceRole.POPUP:
			popup = surface.popup
			
			self.log.info(" popup")
			
			#popup.reposition_event.add(Listener(lambda listener, event: self.manager_notify('reposition', 'POPUP', event, surface)))
			
			surface.data = XdgSurface.from_surface(popup.parent).data.append_surface(surface) # find parent, find scene node from parent's `data` field, create new scene node, assign to popup's `data` field
		
		else:
			self.log.warning(f"unknown xdg surface role {surface.role.name}")
		
		self.surfaces[id(surface.data)] = surface
	
	def surface_destroy(self, listener, event, surface:XdgSurface):
		self.log.info(f"surface destroy {event} {surface}")
		
		if surface.role == XdgSurfaceRole.TOPLEVEL:
			self.desktop_manager.destroy_window(surface)
		
		if self.pointed_surface and self.pointed_surface.is_xdg_surface and (XdgSurface.from_surface(self.pointed_surface).data is surface.data):
			self.log.info("unset pointed surface")
			self.pointed_surface = None
		
		del self.surfaces[id(surface.data)]
		
		if surface.data:
			surface.data.destroy()
	
	def surface_map(self, listener, event, surface:XdgSurface):
		self.log.info(f"surface map {event} {surface}")
		
		if surface.role == XdgSurfaceRole.TOPLEVEL:
			self.desktop_manager.map_window(surface)
		
		self.seat.keyboard_notify_enter(surface.surface, self.keyboards[0])
		
		for output in server.outputs.values():
			output.commit()
	
	def toplevel_update(self, listener, event, surface):
		print("toplevel update")
		if surface.toplevel.app_id in self.desktop_manager.desktop and surface in self.desktop_manager.windows.values():
			self.desktop_manager.destroy_window(surface)
		else:
			self.desktop_manager.update_window(surface)
	
	def new_input(self, listener, input_device:InputDevice):
		"New input device (like keyboard or mouse) was attached to the seat."
		
		self.log.info(f"new input device {input_device.type.name}")
		
		if input_device.type == InputDeviceType.POINTER:
			self.log.info(" pointer")
			
			self.cursor.attach_input_device(input_device)
		elif input_device.type == InputDeviceType.KEYBOARD:
			self.log.info(" keyboard")
			
			keyboard = Keyboard.from_input_device(input_device)
			
			keymap = self.xkb_context.keymap_new_from_names()
			keyboard.set_keymap(keymap)
			keyboard.set_repeat_info(25, 600)
			
			keyboard.modifiers_event.add(Listener(lambda listener, event: self.keyboard_modifiers(listener, event, keyboard)))
			keyboard.key_event.add(Listener(lambda listener, event: self.keyboard_key(listener, event, keyboard)))
			
			self.keyboards.append(keyboard)
		else:
			self.log.warning(f"unknown input device {input_device.type.name}")
		
		capabilities = 0 # TODO: set capabilities based on actual presence of mouse or keyboard
		capabilities |= WlSeat.capability.pointer
		capabilities |= WlSeat.capability.keyboard
		
		#if len(self.keyboards) > 0:
		#	capabilities |= WlSeat.capability.keyboard
		
		self.log.debug(f"seat capabilities: {capabilities}")
		self.seat.set_capabilities(capabilities)
	
	def new_output(self, listener, output:Output):
		"New output device (like a monitor or offscreen buffer) was added to the display."
		
		self.log.info(f"new output device {output.name}")
		
		self.outputs[int(ffi.cast('uintptr_t', output._ptr))] = output
		
		output.destroy_event.add(Listener(lambda listener, _output: self.output_destroy(listener, output)))
		output.frame_event.add(Listener(lambda listener, frame: self.output_frame(listener, frame, output)))
		output.request_state_event.add(Listener(lambda listener, event: self.output_request_state(listener, event)))
		#output.bind_event.add(Listener(lambda listener, *args: self.output_bind(listener, *args, output)))
		#output.damage_event.add(Listener(lambda listener, *args: self.output_damage(listener, *args, output)))
		#output.description_event.add(Listener(lambda listener, *args: self.output_description(listener, *args, output)))
		#output.enable_event.add(Listener(lambda listener, *args: self.output_enable(listener, *args, output)))
		#output.needs_frame_event.add(Listener(lambda listener, *args: self.output_needs_frame(listener, *args, output)))
		#output.precommit_event.add(Listener(lambda listener, *args: self.output_precommit(listener, *args, output)))
		#output.commit_event.add(Listener(lambda listener, *args: self.output_commit(listener, *args, output)))
		#output.present_event.add(Listener(lambda listener, *args: self.output_present(listener, *args, output)))
		
		output.init_render(self.allocator, self.renderer)
		if (mode := output.preferred_mode()) is not None:
			output.set_mode(mode)
		self.output_layout.add_auto(output)
		
		#for _attr in dir(output):
		#	if _attr.startswith('_'): continue
		#	self.log.debug(f" {_attr}: {getattr(output, _attr)}")

		# create default background
		#box = self.output_layout.get_box(output)
		
		#width = 1024
		#height = 768
		
		background = self.scene_tree.append_tree(0, 0)
		#background.append_rect(0, 0, width, height, self.default_background_color)
		#background.append_tree(0, 0)
		self.output_background[int(ffi.cast('uintptr_t', output._ptr))] = background
		
		output.enable()
		#output.commit()
		
		self.desktop_manager.create_desktop(output)
	
	def output_destroy(self, listener, output):
		self.log.info(f"destroy output")
		
		try:
			self.desktop_manager.destroy_desktop(output)
		except AttributeError:
			pass
		
		try:
			self.output_background[int(ffi.cast('uintptr_t', output._ptr))].destroy()
		except KeyError:
			pass
		else:
			del self.output_background[int(ffi.cast('uintptr_t', output._ptr))]
		
		del self.outputs[int(ffi.cast('uintptr_t', output._ptr))]
		if not self.outputs: # last window closed
			self.display.terminate()
	
	def output_frame(self, listener, frame, output):
		"Render a single frame on the provided output device."
		
		#self.log.debug(f"output.frame {frame} {output}")
		scene_output = self.scene.get_scene_output(output)
		if scene_output._ptr:
			scene_output.commit()
			scene_output.send_frame_done(Timespec.get_monotonic_time())
	
	def output_request_state(self, listener, event):
		self.log.debug(f"output.mode {event.state.custom_mode}")
		
		output = event.output
		state = event.state
		#for _attr in dir(state):
		#	if _attr.startswith('_'): continue
		#	self.log.debug(f" {_attr}: {getattr(state, _attr)}")
		
		width = state.custom_mode.width
		height = state.custom_mode.height
		
		try:
			background = self.output_background[int(ffi.cast('uintptr_t', output._ptr))]
		except KeyError:
			background = self.scene_tree.append_tree(0, 0)
			background.append_rect(0, 0, width, height, self.default_background_color)
		else:
			background.set_position(0, 0)
			background[0].set_size(width, height)
		
		self.desktop_manager.resize_desktop(output, width, height)
	
	#def output_bind(self, listener, arg, output):
	#	self.log.debug(f"output.bind {arg} {output}")
	#
	#def output_damage(self, listener, damaged, output):
	#	self.log.debug(f"output.damage {damaged} {output}")
	#
	#def output_description(self, listener, arg, output):
	#	self.log.debug(f"output.description {arg} {output}")
	#
	#def output_enable(self, listener, arg, output):
	#	self.log.debug(f"output.enable {arg} {output}")
	#
	#def output_needs_frame(self, listener, arg, output):
	#	self.log.debug(f"output.needs_frame {arg} {output}")
	#
	#def output_precommit(self, listener, arg, output):
	#	self.log.debug(f"output.precommit {arg} {output}")
	#
	#def output_commit(self, listener, arg, output):
	#	self.log.debug(f"output.commit {arg} {output}")
	#
	#def output_present(self, listener, arg, output):
	#	self.log.debug(f"output.present {arg} {output}")
	
	def cursor_motion(self, listener, event_motion:PointerMotionEvent):
		"Relative cursor motion event. Argument contains `delta_x` and `delta_y` fields."
		
		self.cursor.move(event_motion.delta_x, event_motion.delta_y, input_device=event_motion.pointer.base)
		#self.log.debug(f"relative cursor motion event: {self.cursor.x}, {self.cursor.y}")
		self.idle_notify.notify_activity(self.seat)
		
		self.__pointer_motion(event_motion.time_msec)
	
	def cursor_motion_absolute(self, listener, event_motion_absolute:PointerMotionAbsoluteEvent):
		"Absolute cursor motion event. Argument contains `x` and `y` fields."
		
		self.cursor.warp(WarpMode.AbsoluteClosest, event_motion_absolute.x, event_motion_absolute.y, input_device=event_motion_absolute.pointer.base)
		#self.log.debug(f"absolute cursor motion event: {self.cursor.x}, {self.cursor.y}")
		self.idle_notify.notify_activity(self.seat)
		
		self.__pointer_motion(event_motion_absolute.time_msec)
	
	def __pointer_motion(self, time_msec):
		#pointed_scene_node = None
		pointed_surface = None
		
		node_x_y = self.scene.tree.node.node_at(self.cursor.x, self.cursor.y)
		if node_x_y is not None:
			node, x, y = node_x_y
			
			if node.type == SceneNodeType.BUFFER:
				scene_buffer = SceneBuffer.from_node(node)
				if scene_buffer is not None:
					scene_surface = SceneSurface.from_buffer(scene_buffer)
					if scene_surface is not None:
						pointed_surface = scene_surface.surface
		
		if pointed_surface == self.pointed_surface:
			if pointed_surface:
				self.seat.pointer_notify_motion(time_msec, x, y)
		else:
			if self.pointed_surface and self.pointed_surface.is_xdg_surface:
				xdg_surface = XdgSurface.from_surface(self.pointed_surface)
				if xdg_surface.role == XdgSurfaceRole.TOPLEVEL:
					#xdg_surface.data.raise_to_top()
					xdg_surface.set_activated(False)
					#self.desktop_manager.deactivate()
				#self.manager_notify('deactivate', xdg_surface.role.name, None, xdg_surface)
			
			if pointed_surface:
				self.seat.pointer_notify_enter(pointed_surface, x, y)
				if pointed_surface.is_xdg_surface:
					xdg_surface = XdgSurface.from_surface(pointed_surface)
					if xdg_surface.role == XdgSurfaceRole.TOPLEVEL:
						xdg_surface.data.raise_to_top()
						xdg_surface.set_activated(True)
					#self.manager_notify('activate', xdg_surface.role.name, None, xdg_surface)
				server.seat.keyboard_notify_enter(pointed_surface, server.keyboards[0])
			
			else:
				self.seat.pointer_clear_focus()
		
		if not pointed_surface:
			self.xcursor_manager.load(1.0)
		
		self.pointed_surface = pointed_surface
	
	def cursor_button(self, listener, event:PointerButtonEvent):
		self.seat.pointer_notify_button(event.time_msec, event.button, event.button_state)
		self.log.debug(f"cursor button event: {self.cursor.x}, {self.cursor.y}, {event.button}, {event.button_state}")
		self.idle_notify.notify_activity(self.seat)
		self.log.debug("(end)")
	
	def cursor_axis(self, listener, event):
		self.seat.pointer_notify_axis(event.time_msec, event.orientation, event.delta, event.delta_discrete, event.source)
	
	def cursor_frame(self, listener, event):
		self.seat.pointer_notify_frame()
	
	def keyboard_modifiers(self, listener, event, keyboard:Keyboard):
		self.log.debug(f"keyboard modifiers {event} {keyboard}")
		#keyboard = Keyboard.from_input_device(input_device)
		self.seat.set_keyboard(keyboard)
		self.seat.keyboard_notify_modifiers(keyboard.modifiers)
	
	def keyboard_key(self, listener, key_event:KeyboardKeyEvent, keyboard:Keyboard):
		if not hasattr(self, 'idle_notify'):
			"If the compositor has been closed using key combination, abort sequence; else the key release events would be triggered on finished object."
			listener.remove()
			return
		self.log.debug(f"keyboard key {key_event} {keyboard}")
		self.idle_notify.notify_activity(self.seat)
		self.seat.set_keyboard(keyboard)
		self.seat.keyboard_notify_key(key_event)
	
	def request_set_cursor(self, listener, event):
		self.log.debug("seat request set cursor")
		self.cursor.set_surface(event.surface, event.hotspot)
	
	def request_set_selection(self, listener, event:RequestSetSelectionEvent):
		self.log.debug("seat request set selection")
		self.seat.set_selection(event._ptr.source, event.serial)


if __name__ == '__main__':
	import sys, os, signal
	from subprocess import Popen, PIPE
	
	if len(sys.argv) < 3:
		logging.error(f"Usage: {sys.argv[0]} seat<N> <desktop command...>")
		exit(1)
	
	seat_id = sys.argv[1]
	desktop = sys.argv[2:]
	
	with Server(log=logging, cursor_size=24, seat_id=seat_id) as server:
		server.event_loop.add_signal(signal.SIGINT, lambda signum, _: server.display.terminate())
		
		environ = os.environ.copy()
		if 'DISPLAY' in environ:
			del environ['DISPLAY']
		environ['GDK_BACKEND'] = 'wayland'
		environ['WAYLAND_DISPLAY'] = server.socket.decode()
		server.log.info(f"socket {server.socket.decode()}")
		
		'''
		manager = Popen(*desktop, stdin=PIPE, stdout=PIPE, shell=True, env=environ)
		server.event_loop.add_signal(signal.SIGCHLD, lambda signum, _: server.display.terminate() if manager.poll() is not None else None)
		
		server.manager_in = manager.stdin
		server.manager_out = manager.stdout
		
		def manager_request(msg):
			match msg.split():
				case [message_id, 'map', surface_id]:
					try:
						surface = server.surfaces[int(surface_id, 16)]
					except KeyError:
						return
					surface.data.raise_to_top()
					
					for output in server.outputs.values():
						output.commit()
					
					server.manager_in.write(f"@ {message_id}\n".encode('utf-8'))
					server.manager_in.flush()
				
				case [message_id, 'unmap', surface_id]:
					try:
						surface = server.surfaces[int(surface_id, 16)]
					except KeyError:
						return
					surface.data.lower_to_bottom()
					
					for output in server.outputs.values():
						output.commit()
					
					server.manager_in.write(f"@ {message_id}\n".encode('utf-8'))
					server.manager_in.flush()
				
				case [message_id, 'set_window_geometry', surface_id, x, y, w, h]:
					try:
						surface = server.surfaces[int(surface_id, 16)]
					except KeyError:
						return
					surface.data.set_position(int(x), int(y))
					surface.set_size(int(w), int(h))
					
					for output in server.outputs.values():
						output.commit()
					
					server.manager_in.write(f"@ {message_id}\n".encode('utf-8'))
					server.manager_in.flush()
				
				#case [message_id, 'focus', surface_id]:
				#	try:
				#		surface = server.surfaces[int(surface_id, 16)]
				#	except KeyError:
				#		return
				#	surface.set_activated(True)
				#	server.seat.keyboard_notify_enter(surface.surface, server.keyboards[0])
				#	
				#	for output in server.outputs.values():
				#		output.commit()
				#	
				#	server.manager_in.write(f"@ {message_id}\n".encode('utf-8'))
				#	server.manager_in.flush()
				
				case default:
					print("default", default)	
		
		server.event_loop.add_fd(manager.stdout.fileno(), lambda _a, fd, _b: manager_request(manager.stdout.readline()[:-1].decode('utf-8')))
		'''
		
		#for output in server.outputs.values():
		#	box = output.get_box()
		#	server.desktop_manager.create_desktop(output, box.width, box.height)
		#	#server.manager_notify('new_output', 'OUTPUT', None, output)
		
		server.display.run()
		
		#manager.terminate()
		
		server.log.info("server finished")
	
	logging.info("bye")

