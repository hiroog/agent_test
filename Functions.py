# 2025/06/08 Ogasawara Hiroyuki
# vim:ts=4 sw=4 et:

import os
import inspect
import random

#------------------------------------------------------------------------------

class ToolManager:
    def __init__( self ):
        self.info_list= []
        self.func_map= {}
        self.debug_echo= False

    def get_function_info( self, func ):
        type_to_name= {
            'int': 'int',
            'str': 'string',
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
        properties= {}
        required= []
        for param_name,param in sig.parameters.items():
            param_type= 'string'
            if param.annotation != inspect._empty:
                param_type= param.annotation.__name__
                if param_type in type_to_name:
                    param_type= type_to_name[param_type]
            properties[param_name]= {
                'type': param_type,
            }
            required.append( param_name )
        if len(properties) > 0:
            func_info['parameters']['properties']= properties
            func_info['parameters']['required']= required
        return  { 'type': 'function', 'function': func_info }

    def add( self, func ):
        func_info= self.get_function_info( func )
        self.info_list.append( func_info )
        self.func_map[func.__name__]= func_info,func
        if self.debug_echo:
            print( 'Add: Function "%s"' % func.__name__, func.__doc__ )
        return  func

    def get_tools( self ):
        return  self.info_list

    def call_func( self, func_name, args ):
        if func_name not in self.func_map:
            return  'Function "%s" not found' % func_name
        func_info,func= self.func_map[func_name]
        result= str(func( **args ))
        if self.debug_echo:
            print( 'Call: %s(%s) result=%s' % (func_name,str(args),result), flush=True )
        return  result

tool= ToolManager()

#------------------------------------------------------------------------------

@tool.add
def calc_add( a: int, b: int ) -> int:
    """Add two numbers"""
    return  a + b

@tool.add
def get_weather( city:str ) -> str:
    """Get weather"""
    return  ['晴れ','雨','雷雨','曇り','雪','曇のち晴れ'][random.randrange(0,6)]

#------------------------------------------------------------------------------

def find_file( folder, base_name_lower ):
    for root,dirs,files in os.walk( folder ):
        for name in files:
            if base_name_lower == name.lower():
                return  os.path.join( root, name )
    return  None

def search_file( search_list, base_name ):
    base_name_lower= base_name.lower()
    for dir_name in search_list:
        result= find_file( dir_name, base_name_lower )
        if result:
            return  result
    return  base_name

@tool.add
def read_source_code( file_name: str ) -> str:
    """Read a source code.
    By simply specifying the file name, you can search the Project and Engine folders and read the file content.
    """
    base_name= os.path.basename( file_name )
    project_path= os.environ.get( 'MCP_PROJECT_ROOT', '' )
    engine_path= os.environ.get( 'MCP_ENGINE_ROOT', '' )
    search_list= []
    if project_path != '':
        search_list.append( os.path.join( project_path, 'Source' ) )
        search_list.append( os.path.join( project_path, 'Plugins' ) )
    if engine_path != '':
        search_list.append( os.path.join( engine_path, 'Engine/Source' ) )
        search_list.append( os.path.join( engine_path, 'Engine/Plugins' ) )
    full_name= search_file( search_list, file_name )
    print( 'load:', full_name, flush=True )
    if os.path.exists( full_name ):
        with open( full_name, 'r', encoding='utf-8' ) as fi:
            code= fi.read()
        return  code
    print( 'not found:', full_name, flush=True )
    return  'File "%s" not found' % file_name

#------------------------------------------------------------------------------

def get_tools():
    return  tool

