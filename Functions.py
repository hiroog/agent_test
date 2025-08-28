# 2025/06/08 Ogasawara Hiroyuki
# vim:ts=4 sw=4 et:

import os
import inspect
import random
import re

#------------------------------------------------------------------------------

class ToolManager:
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
        self.func_map[func.__name__]= func_info,func
        if self.debug_echo:
            print( 'Add: Function "%s"' % func.__name__, func.__doc__ )
        return  func

    def select_tools( self, name_list ):
        tool_list= []
        for name in name_list:
            if name in self.func_map:
                print( 'Add: Function "%s"' % name )
                tool_list.append( self.func_map[name][0] )
        self.info_list= tool_list

    def get_tools( self ):
        return  self.info_list

    def call_func( self, func_name, args ):
        if func_name not in self.func_map:
            return  'Function "%s" not found' % func_name
        func_info,func= self.func_map[func_name]
        try:
            result= str(func( **args ))
        except TypeError as e:
            return  'Argument mismatch in tool call. "%s"' % (str(e))
        if self.debug_echo:
            if len(result) <= 128:
                print( 'Call: %s(%s) result=%s' % (func_name,str(args),result), flush=True )
            else:
                print( 'Call: %s(%s) result=%d chars' % (func_name,str(args),len(result)), flush=True )
        return  result

tool= ToolManager()

def get_tools():
    return  tool

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
def read_source_code( file_name:str ) -> str:
    """Read a source code.
    By simply specifying the file name, you can search the Project and Engine folders and read the file content.
    """
    base_name= os.path.basename( file_name )
    search_list= []
    source_root= os.environ.get( 'MCP_SOURCE_ROOT', '' )
    if source_root != '':
        search_list.append( os.path.abspath( source_root ) )
    project_root= os.environ.get( 'MCP_PROJECT_ROOT', '' )
    if project_root != '':
        project_root= os.path.abspath( project_root )
        search_list.append( os.path.join( project_root, 'Source' ) )
        search_list.append( os.path.join( project_root, 'Plugins' ) )
    engine_root= os.environ.get( 'MCP_ENGINE_ROOT', '' )
    if engine_root != '':
        engine_root= os.path.abspath( engine_root )
        search_list.append( os.path.join( engine_root, 'Engine/Source' ) )
        search_list.append( os.path.join( engine_root, 'Engine/Plugins' ) )
    ignore_set= set( ['.','..'] )
    if base_name in ignore_set:
        return  'Invalid filename "%s"' % file_name
    full_name= search_file( search_list, base_name )
    print( 'load:', full_name, flush=True )
    if os.path.exists( full_name ):
        with open( full_name, 'r', encoding='utf-8' ) as fi:
            code= fi.read()
        return  ('** File: %s **\n\n' % base_name) + code
    print( 'not found:', full_name, flush=True )
    return  'File "%s" not found' % file_name

#------------------------------------------------------------------------------

class LogFile:
    def __init__( self, file_name ):
        self.fp= None
        self.file_name= file_name
        self.issue_id= 0
    def open( self ):
        if self.fp is None:
            self.fp= open( self.file_name, 'w', encoding='utf-8' )
    def close( self ):
        if self.fp:
            self.fp.flush()
            self.fp.close()
            self.fp= None
    def append( self, title, file_name, description ):
        if self.fp is None:
            self.open()
        self.issue_id+= 1
        entry= '%d,%s,%s\n%s\n\n' % (self.issue_id,title,file_name,description)
        self.fp.write( entry + '\n' )
        return  self.issue_id

issue_list= None

@tool.add
def create_issue( title:str, description:str, file_name:str ) -> str:
    """Add a new issue to the bug tracking system.

    Args:
        title: Issue title
        description: Issue description. Please include identifiable information such as file names and line numbers in the description along with the details of the issue.
        file_name: Filename
    """
    global issue_list
    issue_id= 0
    if issue_list:
        issue_id= issue_list.append( title, file_name, description )
    print( 'New Issue: %s (%s)' % (title,file_name) )
    print( '  desc: %s' % title, flush=True )
    return  'Issue created : "%s" id=%d' % (title,issue_id)

#------------------------------------------------------------------------------

def grep_files( folder, pat_key, filename, content ):
    result_text= '**Found documents**:\n\n'
    found_files= 0
    for root,dirs,files in os.walk( folder ):
        for name in files:
            full_path= os.path.join( root, name )
            if filename:
                pat= pat_key.search( name )
                if pat:
                    result_text+= '- %s\n' % name
                    found_files+= 1
                    continue
            if content:
                with open( full_path, 'r', encoding='utf-8', errors='ignore' ) as fi:
                    data= fi.read()
                    pat= pat_key.search( data )
                    if pat:
                        result_text+= '- %s\n' % name
                        found_files+= 1
    if found_files == 0:
        result_text= 'File not found\n\n'
    return  result_text

@tool.add
def search_in_files( pattern:str, case_sensitive:bool=True, include_filenames:bool=False ) -> str:
    """Searches documents and file contents and returns a list of filenames of found files. Search patterns can use Python's regular expressions.

    Args:
        pattern: Regular expressions
        case_sensitive: If false, case sensitivity is ignored. The default is true.
        include_filenames: If true, include filenames.
    """
    flags= 0
    if not case_sensitive:
        flags|= re.IGNORECASE
    try:
        pat_key= re.compile( pattern, flags )
    except re.PatternError as e:
        return  str(e)
    folder_root= os.environ.get( 'MCP_FOLDER_ROOT', '' )
    return  grep_files( folder_root, pat_key, include_filenames, True )

#------------------------------------------------------------------------------


