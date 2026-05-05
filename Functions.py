# 2025/06/08 Ogasawara Hiroyuki
# vim:ts=4 sw=4 et:

import os
import inspect
from datetime import datetime

#------------------------------------------------------------------------------

class ToolEnv:
    def __init__( self, src= None ):
        self.env= {}
        if src:
            self.env.update( src )

    def set( self, env_name, value ):
        self.env[env_name]= value

    def get( self, env_name, defvalue= None ):
        if env_name in self.env:
            return  self.env[env_name]
        return  os.environ.get( env_name, defvalue )

    def to_dict( self ):
        return  self.env


class ToolBox:
    def __init__( self ):
        self.info_list= []
        self.func_map= {}
        self.debug_echo= False

    def get_function_info( self, func ):
        type_to_name= {
            'int': 'integer',
            'str': 'string',
            'bool': 'boolean',
            'float': 'number',
        }
        func_info= {
            'name': func.__name__,
            'description': func.__doc__,
            'parameters': {
                'type': 'object',
                'properties': {}
            }
        }
        sig= inspect.signature( func )
        with_env= False
        properties= {}
        required= []
        for param_name,param in sig.parameters.items():
            param_type= 'string'
            if param.annotation != inspect._empty:
                param_type= param.annotation.__name__
                if param_type == 'ToolEnv':
                    with_env= True
                    continue
                if param_type in type_to_name:
                    param_type= type_to_name[param_type]
                else:
                    print( 'Function type error: ', param_type )
            properties[param_name]= {
                'type': param_type,
            }
            required.append( param_name )
        if len(properties) > 0:
            func_info['parameters']['properties']= properties
            func_info['parameters']['required']= required
        return  { 'type': 'function', 'function': func_info },with_env

    def add( self, func ):
        func_info,with_env= self.get_function_info( func )
        self.func_map[func.__name__]= func_info,with_env,func
        if self.debug_echo:
            #print( 'Load: Function "%s"' % func.__name__, func.__doc__ )
            print( 'Load: Function "%s"' % func.__name__ )
        return  func

    def tool( self, func= None ):
        if func is None:
            return  self.add
        return  self.add( func )

    def select_tools( self, name_list ):
        self.info_list= self.get_tools( name_list )
        return  self.info_list

    def get_tools( self, name_list= None ):
        if name_list is None:
            return  self.info_list
        tool_list= []
        for name in name_list:
            if name in self.func_map:
                if self.debug_echo:
                    print( 'Add: Function "%s"' % name )
                tool_list.append( self.func_map[name][0] )
        return  tool_list

    def call_func( self, func_name, args, env= None ):
        if func_name not in self.func_map:
            return  'Function "%s" not found' % func_name
        func_info,with_env,func= self.func_map[func_name]
        try:
            if with_env:
                result= str(func( env, **args ))
            else:
                result= str(func( **args ))
        except TypeError as e:
            return  'Argument mismatch in tool call. "%s"' % (str(e))
        if self.debug_echo:
            if len(result) <= 128:
                print( 'Call: %s(%s) result=%s' % (func_name,str(args),result), flush=True )
            else:
                print( 'Call: %s(%s) result=%d chars' % (func_name,str(args),len(result)), flush=True )
        return  result

mcp= ToolBox()

def get_toolbox():
    return  mcp

#------------------------------------------------------------------------------

@mcp.tool()
def get_current_datetime() -> str:
    """
    Returns the current date and time in the format YYYY-MM-DD HH:MM:SS."
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

#------------------------------------------------------------------------------

