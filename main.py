#!/usr/bin/python3

import sys
import signal
import dbus
from gi.repository import GLib
from dbus.mainloop.glib import DBusGMainLoop


import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst

DBusGMainLoop(set_as_default=True)
Gst.init(None)

loop = GLib.MainLoop()

bus = dbus.SessionBus()
screen_cast_iface = 'org.gnome.Mutter.ScreenCast'
screen_cast_session_iface = 'org.gnome.Mutter.ScreenCast.Session'
screen_cast_stream_iface = 'org.gnome.Mutter.ScreenCast.Session'

screen_cast = bus.get_object(screen_cast_iface,
                             '/org/gnome/Mutter/ScreenCast')
session_path = screen_cast.CreateSession([], dbus_interface=screen_cast_iface)
print("session path: %s"%session_path)
session = bus.get_object(screen_cast_iface, session_path)
format_element = ""

if len(sys.argv) == 6 and sys.argv[1] == '-a':
    [_, _, x, y, width, height] = sys.argv
    stream_path = session.RecordArea(
        int(x), int(y), int(width), int(height),
        dbus.Dictionary({'is-recording': dbus.Boolean(True, variant_level=1),
                         'cursor-mode': dbus.UInt32(0, variant_level=1)}, signature='sv'),
        dbus_interface=screen_cast_session_iface)
elif len(sys.argv) == 2 and sys.argv[1] == '-w':
    stream_path = session.RecordWindow("",
        dbus.types.Dictionary({'cursor-mode': dbus.UInt32(1, variant_level=1)}),
        dbus_interface=screen_cast_session_iface)
elif len(sys.argv) == 4 and sys.argv[1] == '-v':
    [_, _, width, height] = sys.argv
    stream_path = session.RecordVirtual(
        dbus.Dictionary({'is-platform': dbus.Boolean(True, variant_level=1),
                         'cursor-mode': dbus.UInt32(1, variant_level=1)}, signature='sv'),
        dbus_interface=screen_cast_session_iface)
    format_element = "video/x-raw,max-framerate=60/1,width=%d,height=%d !"%(
        int(width), int(height))
else:
    stream_path = session.RecordMonitor(
        "", dbus.types.Dictionary({'cursor-mode': dbus.UInt32(1, variant_level=1),}),
        dbus_interface=screen_cast_session_iface)

print("stream path: %s"%stream_path)
stream = bus.get_object(screen_cast_iface, stream_path)
pipeline = None

def terminate():
    global pipeline, cap
    print("pipeline: " + str(pipeline))
    if pipeline is not None:
        print("draining pipeline")
        pipeline.send_event(Gst.Event.new_eos())
        pipeline.set_state(Gst.State.NULL)
    print("stopping")
    session.Stop(dbus_interface=screen_cast_session_iface)
    loop.quit()
    
    if cap is not None:
      cap.release()
    

def on_message(bus, message):
    global pipeline
    type = message.type
    print("message pipeline: " + str(pipeline))
    if type == Gst.MessageType.EOS or type == Gst.MessageType.ERROR:
        terminate()

def on_pipewire_stream_added(node_id):
    # CURRENT MAINLOOP #
    
    print("added", node_id)
    global pipeline, cap
    
    import cv2
    import moderngl as gl
    import moderngl_window as glw
    import numpy as np
    import time

    from PIL import Image
    cap = cv2.VideoCapture(f'pipewiresrc path={node_id} ! videoconvert ! appsink', cv2.CAP_GSTREAMER)




    class Test(glw.WindowConfig):
        gl_version = (3, 3)
        window_size = (1920, 1080)
        title = "Two displays"

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            # Do initialization here
            self.prog = self.ctx.program(vertex_shader='''
            #version 310 es
            in vec2 in_vert;
            in vec2 in_uv;
            
            out mediump vec2 uv0;
            
            void main() {
              uv0 = in_uv;
              gl_Position = vec4(in_vert,0,1);
            }
            ''',
            fragment_shader='''
            #version 310 es
            
            in mediump vec2 uv0;
            
            layout(location=0) uniform sampler2D img;
            
            out lowp vec4 f_color;
            
            void main(){
              f_color = vec4(texture(img, uv0).bgr,1);
            }
            ''')
            
            aspecto = self.wnd.size[0]/self.wnd.size[1]
            buf = self.ctx.buffer(np.asarray([
              1,0.5*3/4-0.2, 1,0,
              -1,0.5*3/4-0.2, 0,0,
              -1,-0.5*3/4-0.2, 0,1,
              
              -1,-0.5*3/4-0.2, 0,1,
              1,-0.5*3/4-0.2, 1,1,
              1,0.5*3/4-0.2, 1,0,
            
            ],dtype='f4').tobytes())
            self.vao = self.ctx.vertex_array(self.prog, buf, 'in_vert', 'in_uv')
            self.texture = self.ctx.texture(self.wnd.size, 4)
            self.texture2 = self.ctx.texture((1280,720), 3)
            

        def render(self, times, frametime):
            # This method is called every frame
            ret, frame = cap.read()
            
            frame = cv2.resize(frame, (1280,720))
            #frame = frame.tobytes()
            
            #img = Image.fromarray(frame)
            #img = img.convert('RGBA')
            
            #img.show()
            #lt = time.time()
            self.texture2.write(frame.tobytes())
            #print(1000*(time.time()-lt))
            self.texture2.use(0)#bind_to_image(0)
            
            #print(np.frombuffer(self.texture2.read(),dtype='uint8'))
            #exit()
            self.wnd.fbo.use()
            self.wnd.fbo.viewport = (self.wnd.size[0]//16,0, self.wnd.size[0]//16*6,self.wnd.size[1])
            self.vao.render()
            
            self.wnd.fbo.viewport = (self.wnd.size[0]//2+self.wnd.size[0]//16,0, self.wnd.size[0]//16*6,self.wnd.size[1])
            self.vao.render()

    # Blocking call entering rendering/event loop
    glw.run_window_config(Test)
    terminate()
    ##################

cap = None

def anyp(node_id):
  import os
  print(os.path.exists(node_id))
stream.connect_to_signal("PipeWireStreamAdded", on_pipewire_stream_added)

session.Start(dbus_interface=screen_cast_session_iface)


try:
    loop.run()
except KeyboardInterrupt:
    print("interrupted")
    terminate()
