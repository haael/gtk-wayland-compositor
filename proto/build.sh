#!/bin/bash


PROTO="gwayco"


wayland-scanner client-header "$PROTO.xml" "${PROTO}_client.h"
wayland-scanner server-header "$PROTO.xml" "${PROTO}_server.h"
wayland-scanner enum-header "$PROTO.xml" "${PROTO}_enum.h"
wayland-scanner private-code "$PROTO.xml" "$PROTO.c"

#cat <<EOF >>"$PROTO.c"
#const struct wl_interface* get_desktop_manager_interface() {
#	return &desktop_manager_interface;
#}
#
#EOF

gcc -shared -o "${PROTO}.so" "$PROTO.c"

./generate-py-sources server "$PROTO"


exit


# Step 4: Create Python bindings using CFFI
PYTHON_BINDINGS_DIR="python_bindings"
mkdir -p $PYTHON_BINDINGS_DIR

cat > $PYTHON_BINDINGS_DIR/desktop_manager_build.py <<EOL
from cffi import FFI

ffibuilder = FFI()

ffibuilder.set_source("_desktop_manager", None)

ffibuilder.cdef(\"""
    // Include the generated C headers here
    #include "$CLIENT_HEADER"
    #include "$SERVER_HEADER"
\""")

if __name__ == "__main__":
    ffibuilder.compile(verbose=True)
EOL

# Step 5: Build and install using Meson
MESON_BUILD_DIR="build"
mkdir -p $MESON_BUILD_DIR
cd $MESON_BUILD_DIR

meson setup --buildtype=release ..
ninja
sudo ninja install

cd ..

# Step 6: Install Python bindings
pip install $PYTHON_BINDINGS_DIR
