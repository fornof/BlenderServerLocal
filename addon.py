bl_info = {
    "name": "Bool Mod Apply Tool",
    "author": "Robert Fornof",
    "version": (1, 4),
    "blender": (2, 8, 0),
    "location": "View3D > Tool_Tab> BoolMod",
    "description": "Set boolean",
    "warning": "",
    "wiki_url": "",
    "category": "Object"}
import threading
import bmesh
import http.server
import socketserver
import argparse
import re
from ast import literal_eval as make_tuple
from http.server import HTTPServer, BaseHTTPRequestHandler

from bpy.props import (StringProperty,
                       BoolProperty,
                       IntProperty,
                       FloatProperty,
                       FloatVectorProperty,
                       EnumProperty,
                       PointerProperty,
                       )
from bpy.types import (Panel,
                       Operator,
                       AddonPreferences,
                       PropertyGroup,
                       )
import bpy
from bpy.app.handlers import persistent
import json
import bmesh
class pyQuery():
    def __init__(self):
        self.functions= self._make_function_list()
        
    def _make_function_list(self):
        import inspect
        fxs = {}
        functions = inspect.getmembers(pyQuery, predicate= inspect.isfunction)
        for fx in functions:
            if fx[0][0] =="_":
                continue
            fxs[fx[0]]= fx[1]
        return fxs
    
    def message(self,message):
        print(message)
        return message
    
    def _add_mesh(self,name, verts, faces, edges=[], col_name="Collection", location=(0,0,0)):
        mesh = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(mesh.name, mesh)
        col = bpy.data.collections.get(col_name)
        col.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        mesh.from_pydata(verts, edges, faces) 
        obj.location = location   
    
    def preferences(self, first,key,value):
        if first == 'inputs':
            return setattr(bpy.context.preferences.inputs, key, value)
        else:
            return "not implemented"
        
    def key(self,id, type='location', frame=None, options=""):
        allowed = ['location','rotation_euler','rotation_quaternion','scale', 'name']
        if not id:
            id = bpy.context.object
        else:
            id= bpy.context.scene.objects[id]
            # index : Defaults to -1 which will key all indices or a single channel if the property is not an array.
        id.keyframe_insert(type, index=-1, frame=frame, group="", options=options)
            
    def mod(self,id,type='location', value=None):  
        allowed = ['location','rotation_euler','rotation_quaternion','scale', 'name']
        if not id:
            id = bpy.context.object
        else:
            id= bpy.context.scene.objects[id]
        if not value:
            print(bpy.context.object.location)
            return bpy.context.object.location
        if type in allowed: 
            return setattr(id ,type,value)
            
    def _context(self, bpy_context_string, value):
        context= bpy.context 
        items = bpy_context_string.split(".")
        for item in items:
            context = getattr(context,item)
        context = value

    def select(self,id):
        objectToSelect = None
        try:
            items_currently_selected = bpy.context.view_layer.objects.selected
            if len(items_currently_selected) ==1:
                items_currently_selected[0].select_set(False)
            elif len(items_currently_selected) > 1:
                for item in items_currently_selected:
                    item.select_set(False)
            objectToSelect = bpy.data.objects[id]
            objectToSelect.select_set(True)    
            bpy.context.view_layer.objects.active = objectToSelect
        except Exception as e:
            print("select error"+str(e))
            return False
        return objectToSelect

    def add(self, type,id="serverArt", location=(0,0,0)):
        print("add params",self, type, id, location)
       
        if type == 'CUBE':
            verts = [( 1.0,  1.0,  0.0-1), 
             ( 1.0, -1.0,  0.0-1),
             (-1.0, -1.0,  0.0-1),
             (-1.0,  1.0,  0.0-1),
             ( 1.0,  1.0,  2.0-1), 
             ( 1.0, -1.0,  2.0-1),
             (-1.0, -1.0,  2.0-1),
             (-1.0,  1.0,  2.0-1)
             ]
            faces = [[0,1,2,3],[4,5,6,7],[0,4,5,1], [1,5,6,2],[2,6,7,3],[3,7,4,0]]
            col_name= bpy.data.collections[0].name
            self._add_mesh(id, verts, faces,[], col_name, location)
            return
        elif type == "POINT" or type == "SUN" or type =="SPOT" or type == "AREA" or type == "HEMI":
            light_data = bpy.data.lights.new(name=id, type=type)
            light_data.energy = 30
            # create new object with our light datablock
            light_object = bpy.data.objects.new(name=id, object_data=light_data)
            # link light object
            bpy.context.collection.objects.link(light_object)
            # make it active 
            bpy.context.view_layer.objects.active = light_object
            #change location
            light_object.location = location
            # update scene, if needed
            dg = bpy.context.evaluated_depsgraph_get() 
            dg.update()   
        else:
            print("add not implemented for type:" + type )
    def health(self):
        print("healthy")        
            
    def delete(self,id):
        print("id to delete",id)
        try:
            # Deselect all
    #        if not fast:
    #            bpy.ops.object.select_all(action='DESELECT')
    #            bpy.data.objects[id].select_set(True) # Blender 2.8x
    #            bpy.ops.object.delete()
    #            return 
            # this does things super fast, but does not have an undo with it. I need that undo homis 
            objs = bpy.data.objects
            objs.remove(objs[id], do_unlink=True)
        except Exception as e:
            print("Delete error:"+str(e))
            return False
        return True
    
    def _filterargs(self,args):
        args_return = []
        for arg in args:
            for item in arg:
                if item == "":
                    continue
                if "(" in item:
                    args_return.append(make_tuple(item))
                    continue
                
                args_return.append(re.sub(r"[\'\"]", "", item))
     
         #arg.replace("\'","").replace("\"","")
        print("args_return" ,args_return)
        return args_return
    
    def _handleLine(self,line):
       # print(self.functions)
        matcher = re.findall(r"(\w+)\((.*)\)", line)
        print("mtxr",matcher)
        for match in matcher:
            print("matches", match[0], match[1])
            fx  = match[0]
            args = re.findall(r"[\'\"]?([\w]+)[\'\"]?,?([\w=]?\([0-9a-zA-Z,]+\))?,?",  match[1])
            print("args",args)
            if args == "":
                print("none args")
                self.functions[fx]()
            else:
                args = self._filterargs(args)
                self.functions[fx](self,*args)
            
    def _validateExecute(self,data):
        for line in data.split(";"):
            try:
               self._handleLine(line)
            except Exception as e:
                print("error in execution:"+ str(e))
                return False
        return True
                
query = pyQuery()
class S(BaseHTTPRequestHandler):
    
    def _set_headers(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def _html(self, message):
        """This just generates an HTML document that includes `message`
        in the body. Override, or re-write this do do more interesting stuff.
        """
        content = f"<html><body><h1>{message}</h1></body></html>"
        return content.encode("utf8")  # NOTE: must return a bytes object!
    def validateExecute(self, data):
        return query._validateExecute(data)
        
    def do_GET(self):
        self._set_headers()
        self.wfile.write(self._html("hi!"))

    def do_HEAD(self):
        self._set_headers()
    
    def do_OPTIONS(self):
        self._set_headers()
        print("OPTIONS entered!")
       # self.wfile.write(self._html("hi!"))
            
    def do_POST(self):
        content_length = int(self.headers['Content-Length']) # <---Gets the size of data
        post_data = self.rfile.read(content_length) # <--- Gets the data itself
        try:
            data=json.loads(post_data)
            print("json is", data['data'])
            if not bpy.context.scene.isPassthrough:
                self.validateExecute(data['data'])
            else:
                x= bpy.context.scene.custom.add()
                x.code = data['data']
                x.id = "RobertRocks"
                x.use_this = True
                
        except Exception as e:
            print(str(e))
            self._set_headers()
            self.wfile.write("error, something went wrong when parsing".encode("utf8"))
            return -1
        
        self._set_headers()
        if result:
            self.wfile.write("Success!".encode("utf8"))
        else: 
            self.wfile.write("Failed".encode("utf8"))
        
threads = []
class StartServer():
    def getServerPort(self):
        if bpy.data.scenes['Scene']['serverPort'] <0:
            return 8000
        return bpy.data.scenes['Scene']['serverPort']
    
    def __init__(self):
        
        self.port = self.getServerPort()
        self.handler = S
        self.httpd = None
        self._verbose = True
        self._addon = "server_staff"
        self._server_thread = None
        self._run_server = True
        
    def start_async_server(self, now=False, callback=None):
        try:
            self.stop_async_server()
        except Exception as ex:
            print("stop failed... perhaps not started? oh well, keep going")
        """Start a background thread which will check for updates"""
        if self._verbose:
            print("{} updater: Starting background server thread".format(self._addon))
        _server_thread = threading.Thread(target=self.async_server, args=(now,callback,))
        _server_thread.daemon = True
        self._server_thread = _server_thread
        threads.append(_server_thread)
        _server_thread.start()
    
    

    
    def async_server(self,now ,callback = None):
       
        print("server goes here")
        self.handler = S
        #global args
        self.httpd = socketserver.TCPServer(("", self.port), self.handler)
        print("serving at port", self.port)
        self.httpd.serve_forever(poll_interval=0.5)
#        while self._run_server and args['run_me'] :
#            print("handling request", self._run_server)
#            #httpd.handle_request()
#           
#            print("handling rend of request", self._run_server)
        print("server stopped") 
#        args['run_me'] = True
        return 0
        
             
    def stop_async_server(self,now =None ,callback = None):
        self.httpd.shutdown()
        self.httpd.server_close()
       
#        self._run_server = False
#        args['run_me'] = False
#        print("stop hit")
        
server = StartServer()

# dir(threading.enumerate()[0].stop())

#------------------- FUNCTIONS------------------------------


def ShowMessageBox(message = "", title = "Message Box", icon = 'INFO'):

    def draw(self, context):
        self.layout.label(text=message)

    bpy.context.window_manager.popup_menu(draw, title = title, icon = icon)

def handleAllowDeny(isDeny=True):
     codes = bpy.context.scene.custom
     what_is_left = []
     i = 0
     for code in codes:
         if code.use_this:
             if isDeny:
                 bpy.context.scene.custom.remove(i)
             else:
                data = query.validateExecute(code.code)
                print("executed", data)    
                bpy.context.scene.custom.remove(i)
         else:
             pass 
         i = i+1
    
def Operation(context,operation):
    ''' Select start and end of server '''
    if operation == "AllowScript":
        print("allow")
        handleAllowDeny(isDeny=False)
        return {'FINISHED'}
    if operation == "DenyScript":
        print("deny")
        handleAllowDeny(isDeny=True)
        return {'FINISHED'}
    if operation == "ServerStart":
        server.start_async_server()
        return {'FINISHED'}
    
    if operation == "ServerEnd":
        server.stop_async_server()
        return {'FINISHED'} 
    
    if operation == "ServerExecute":
        data = query._validateExecute(context.scene.my_string_prop)
        print("executed", data)    
        return {'FINISHED'}
  
           
#------------------- OPERATOR CLASSES ------------------------------                
# Mirror Tool                 



class ServerExecute(bpy.types.Operator):
    """This executes the selected object"""
    

    bl_idname = "object.serverexecute"
    bl_label = "SERVEREXECUTE"

    @classmethod
    def poll(cls, context):
        return True
    
    def execute(self, context):
        Operation(context,"ServerExecute")
        return {'FINISHED'}
    
    
class ServerEnd(bpy.types.Operator):
    """This  adds a Intersect modifier"""
    bl_idname = "object.serverend"
    bl_label = "SERVEREND"

    @classmethod
    def poll(cls, context):
        return  True
    
    def execute(self, context):
        Operation(context,"ServerEnd")
        return {'FINISHED'}

class ServerStart(bpy.types.Operator):
    """This  add a difference boolean modifier"""
    bl_idname = "object.serverstart"
    bl_label = "ServerStart"

    @classmethod
    def poll(cls, context):
        return True
    
    def execute(self, context):
        Operation(context,"ServerStart")
        return {'FINISHED'}

class AllowScript(bpy.types.Operator):
    """This allows a script to run"""
    bl_idname = "object.allow_script"
    bl_label = "AllowScript"

    @classmethod
    def poll(cls, context):
        return True
    
    def execute(self, context):
        Operation(context,"AllowScript")
        return {'FINISHED'}
    
class DenyScript(bpy.types.Operator):
    """This denies a script to run"""
    bl_idname = "object.deny_script"
    bl_label = "DenyScript"

    @classmethod
    def poll(cls, context):
        return True
    
    def execute(self, context):
        Operation(context,"DenyScript")
        return {'FINISHED'}



#------------------- MENU CLASSES ------------------------------  

class BooleanMenu(bpy.types.Menu):
    bl_label = "Mirror_Mirror_Tool_MT_"
    bl_idname = "OBJECT_MT_mirror"
    
    def draw(self, context):
        layout = self.layout


    def execute(self, context):
        return {'FINISHED'}     
    
class SimplePropConfirmOperator(bpy.types.Operator):
    """Execute"""
    bl_idname = "my_category.custom_confirm_dialog"
    bl_label = "Do you really want to do that?"
    bl_options = {'REGISTER', 'INTERNAL'}


    @classmethod
    def poll(cls, context):
        return True #return bpy.context.scene.isPassthrough 

    def execute(self, context):
        self.report({'INFO'}, "YES!")
        return {'FINISHED'}

    def invoke(self, context, event):
        #return context.window_manager.invoke_props_dialog(self)
        pass

    def draw(self, context):
        row = self.layout



class OBJECT_PT_CustomPanel(bpy.types.Panel):
    bl_label = "My Panel"
    bl_idname = "OBJECT_PT_custom_panel"
    bl_space_type = "VIEW_3D"   
    bl_region_type = "UI"
    bl_category = "Tools"
    bl_context = "objectmode"
    
    @classmethod
    def poll(cls, context):
        return bpy.context.scene.isPassthrough 

    def draw(self, context):
        layout = self.layout
        layout.operator(AllowScript.bl_idname)
        layout.operator(DenyScript.bl_idname)
        for item in bpy.context.scene.custom:
            layout.prop(item,'use_this', text=item.code*5)
    

class CustomProp(bpy.types.PropertyGroup):
    '''name = StringProperty() '''
    id = bpy.props.IntProperty()
    code = bpy.props.StringProperty()
    use_this=bpy.props.BoolProperty()
#    object = bpy.props.PointerProperty(
#        name="Object",
#        type=bpy.types.Object,
#    )


 
class OBJECT_PT_property_example(bpy.types.Panel):
    #"[note]: Add a mirror on the x, y , or z axis using : ALT+SHIFT+X , ALT+SHIFT+Y, ALT+SHIFT+Z in object mode"
    bl_label = "Server"
    bl_idname = "STUFF_PT_Server_Tool"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Server"
    bl_context = "objectmode"
   
    def draw(self,context):
        layout = self.layout
        box = layout.box()

        box.label(text="Port to listen on for server")
        box.prop(context.scene,'serverPort',text="Port")
        box.label(text="Server items:",icon = "MODIFIER")    
        box.operator(ServerStart.bl_idname ,icon = "ZOOM_IN")
        box.operator(ServerEnd.bl_idname ,icon = "ZOOM_IN")
        box.operator("object.serverexecute", icon = "ZOOM_IN")
#       box.operator(ExecuteCode.bl_idname ,icon = "ZOOM_IN")
        box.prop(context.scene,'my_string_prop',text="")
        layout.prop(context.scene,'isPassthrough', text="Use a command list")
       
        box.separator()    
      
     

        
         
    #---------- Tree Viewer--------------
def VIEW3D_BooleanMenu(self, context):
    self.layout.menu(BooleanMenu.bl_idname)
    
#------------------- REGISTER ------------------------------      
addon_keymaps = []

def register():
    
    bpy.types.Scene.my_string_prop = bpy.props.StringProperty \
      (
        name = "My String",
        description = "My description",
        default = "default"
      )
    bpy.types.Scene.serverPort = bpy.props.IntProperty \
      (
     
      )
    bpy.types.Scene.isPassthrough = bpy.props.BoolProperty()
      
    # Operators
#    bpy.types.Scene.isapply = bpy.props.BoolProperty(
#        name="Apply Modifier",
#        description="Apply modifier on selected",
#        default = True)
    bpy.utils.register_class(CustomProp)
    bpy.utils.register_class(OBJECT_PT_CustomPanel)
    bpy.utils.register_class(SimplePropConfirmOperator)
    bpy.utils.register_class(DenyScript)
    bpy.utils.register_class(AllowScript)
    bpy.utils.register_class(ServerStart)
    bpy.utils.register_class(ServerEnd)
    bpy.utils.register_class(ServerExecute)
    bpy.types.Scene.custom = bpy.props.CollectionProperty(type=CustomProp)
    #Append 3DVIEW Menu
    #bpy.utils.register_class(BooleanMenu)
    #bpy.types.VIEW3D_MT_object.append(VIEW3D_BooleanMenu)
    
    # Append 3DVIEW Tab
    bpy.utils.register_class(OBJECT_PT_property_example)
    
    # handle the keymap
    wm = bpy.context.window_manager
#    km = wm.keyconfigs.addon.keymaps.new(name='Object Mode', space_type='EMPTY')
#    kmi = km.keymap_items.new(ServerStart.bl_idname, 'U', 'PRESS', alt=True, shift = True)
#    addon_keymaps.append((km, kmi))

#    km = wm.keyconfigs.addon.keymaps.new(name='Object Mode', space_type='EMPTY')
#    kmi = km.keymap_items.new(Intersect.bl_idname, 'I', 'PRESS', alt=True, shift = True)
#    addon_keymaps.append((km, kmi))

#    km = wm.keyconfigs.addon.keymaps.new(name='Object Mode', space_type='EMPTY')
#    kmi = km.keymap_items.new(Difference.bl_idname, 'D', 'PRESS', alt=True, shift = True)
#    addon_keymaps.append((km, kmi))

def unregister():
    
    #bpy.utils.unregister_class(BooleanMenu)
    bpy.utils.unregister_class(OBJECT_PT_property_example)
    #bpy.types.VIEW3D_MT_object.remove(VIEW3D_BooleanMenu)
        
    #Operators
    bpy.utils.unregister_class(DenyScript)
    bpy.utils.unregister_class(AllowScript)
    bpy.utils.unregister_class(SimplePropConfirmOperator)
    bpy.utils.unregister_class(OBJECT_PT_CustomPanel)
    bpy.utils.unregister_class(StartServer)
    bpy.utils.unregister_class(ServerStart)
    bpy.utils.unregister_class(ServerEnd)
    bpy.utils.unregister_class(ServerExecute )
    del bpy.types.Scene.custom 
    del bpy.types.Scene.isPassthrough
    del bpy.types.Scene.serverPort
    del bpy.types.Scene.my_string_prop
   # bpy.app.handlers.scene_update_post.remove(HandleScene)
    #bpy.types.VIEW3D_MT_object.remove(VIEW3D_BooleanMenu)
    
    # Keymapping
    # handle the keymap
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    

if __name__ == "__main__":
    try:
        unregister()
    except:
        pass
    register()